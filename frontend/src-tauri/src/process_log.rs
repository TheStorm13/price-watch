//! Bounded output of owned processes: one file, no archives or line buffers.
use std::{
    fs::{File, OpenOptions},
    io::{self, Read, Seek, SeekFrom, Write},
    os::{fd::OwnedFd, unix::net::UnixStream},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
pub const MAX_LOG_BYTES: u64 = 10 * 1024 * 1024;

struct LogWriter {
    path: PathBuf,
    file: Option<File>,
    size: u64,
    limit: u64,
}
impl LogWriter {
    fn new(path: &Path, limit: u64) -> io::Result<Self> {
        let file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(path)?;
        Ok(Self {
            path: path.into(),
            file: Some(file),
            size: 0,
            limit,
        })
    }
    fn write(&mut self, mut bytes: &[u8]) -> io::Result<()> {
        if self.file.is_none() {
            let file = OpenOptions::new()
                .create(true)
                .write(true)
                .open(&self.path)?;
            self.size = file.metadata()?.len();
            self.file = Some(file);
        }
        let file = self.file.as_mut().unwrap();
        file.seek(SeekFrom::Start(self.size))?;
        while !bytes.is_empty() {
            if self.size >= self.limit {
                file.set_len(0)?;
                file.seek(SeekFrom::Start(0))?;
                self.size = 0;
            }
            let count = bytes.len().min((self.limit - self.size) as usize);
            file.write_all(&bytes[..count])?;
            self.size += count as u64;
            bytes = &bytes[count..];
        }
        Ok(())
    }
}

pub struct LogDrain {
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}
impl LogDrain {
    pub fn attach(command: &mut Command, path: &Path) -> Result<Self, String> {
        Self::attach_with_limit(command, path, MAX_LOG_BYTES)
            .map_err(|e| format!("Не удалось подготовить {}: {e}", path.display()))
    }
    fn attach_with_limit(command: &mut Command, path: &Path, limit: u64) -> io::Result<Self> {
        if limit == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "zero log limit",
            ));
        }
        let mut writer = LogWriter::new(path, limit)?;
        let (mut read, write) = UnixStream::pair()?;
        read.set_read_timeout(Some(Duration::from_millis(100)))?;
        command
            .stdout(Stdio::from(OwnedFd::from(write.try_clone()?)))
            .stderr(Stdio::from(OwnedFd::from(write)));
        let stop = Arc::new(AtomicBool::new(false));
        let signal = Arc::clone(&stop);
        let thread = thread::spawn(move || {
            let mut buffer = [0; 64 * 1024];
            let mut last_error = None;
            let mut stopping = None;
            loop {
                if signal.load(Ordering::Acquire) {
                    let start = stopping.get_or_insert_with(Instant::now);
                    if start.elapsed() > Duration::from_millis(200) {
                        break;
                    }
                }
                match read.read(&mut buffer) {
                    Ok(0) => break,
                    Ok(count) => {
                        if let Err(error) = writer.write(&buffer[..count]) {
                            writer.file = None;
                            if last_error
                                .map_or(true, |at: Instant| at.elapsed() >= Duration::from_secs(60))
                            {
                                eprintln!("Не удалось записать журнал процесса: {error}");
                                last_error = Some(Instant::now());
                            }
                        }
                    }
                    Err(error)
                        if matches!(
                            error.kind(),
                            io::ErrorKind::WouldBlock
                                | io::ErrorKind::TimedOut
                                | io::ErrorKind::Interrupted
                        ) =>
                    {
                        if signal.load(Ordering::Acquire) {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });
        Ok(Self {
            stop,
            thread: Some(thread),
        })
    }
}
impl Drop for LogDrain {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounds_continuous_output_and_replaces_previous_session() {
        let dir = std::env::temp_dir().join(format!("pw-log-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("child.log");
        let mut command = Command::new("python3");
        command.args([
            "-c",
            "import os; os.write(1,b'x'*300000); os.write(2,b'END')",
        ]);
        let log = LogDrain::attach_with_limit(&mut command, &path, 1024).unwrap();
        command.spawn().unwrap().wait().unwrap();
        drop(log);
        let data = std::fs::read(&path).unwrap();
        assert!(data.len() <= 1024);
        assert!(data.ends_with(b"END"));
        let mut command = Command::new("true");
        let log = LogDrain::attach_with_limit(&mut command, &path, 1024).unwrap();
        command.spawn().unwrap().wait().unwrap();
        drop(log);
        assert!(std::fs::read(&path).unwrap().is_empty());
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn shutdown_does_not_wait_for_inherited_descriptors() {
        let path = std::env::temp_dir().join(format!("pw-log-stop-{}", std::process::id()));
        let mut command = Command::new("true");
        let log = LogDrain::attach(&mut command, &path).unwrap();
        // Command still owns open write descriptors; no EOF is available.
        let start = Instant::now();
        drop(log);
        assert!(start.elapsed() < Duration::from_secs(1));
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn disk_failure_does_not_block_a_verbose_child() {
        let mut command = Command::new("python3");
        command.args(["-c", "import os; os.write(1,b'x'*300000)"]);
        let log = LogDrain::attach_with_limit(&mut command, Path::new("/dev/full"), 1024).unwrap();
        let mut child = command.spawn().unwrap();
        let start = Instant::now();
        loop {
            if let Some(status) = child.try_wait().unwrap() {
                assert!(status.success());
                break;
            }
            if start.elapsed() > Duration::from_secs(5) {
                child.kill().unwrap();
                child.wait().unwrap();
                panic!("log failure blocked child");
            }
            thread::sleep(Duration::from_millis(10));
        }
        drop(log);
    }
}
