use std::{
    env,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    os::{
        fd::AsRawFd,
        unix::fs::{OpenOptionsExt, PermissionsExt},
    },
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

pub struct NativeServices {
    _lock: File,
    api: ManagedChild,
    display: ManagedChild,
    postgres: ManagedChild,
    pub database_url: String,
    pub api_port: u16,
    pub api_token: String,
    pub display_number: u16,
    pub xauthority: PathBuf,
    pg_dump: PathBuf,
    socket_dir: PathBuf,
    pg_port: u16,
    backup_dir: PathBuf,
}

impl Drop for NativeServices {
    fn drop(&mut self) {
        if let Err(error) = self.backup_database() {
            eprintln!("Не удалось сохранить резервную копию локальной базы: {error}");
        }
    }
}

struct ManagedChild(Child);

impl Drop for ManagedChild {
    fn drop(&mut self) {
        unsafe { libc::kill(self.0.id() as i32, libc::SIGTERM) };
        let deadline = Instant::now() + Duration::from_secs(5);
        while matches!(self.0.try_wait(), Ok(None)) && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(100));
        }
        if matches!(self.0.try_wait(), Ok(None)) {
            let _ = self.0.kill();
        }
        let _ = self.0.wait();
    }
}

fn private_dir(path: &Path) -> Result<(), String> {
    fs::create_dir_all(path)
        .map_err(|error| format!("Не удалось создать {}: {error}", path.display()))?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("Не удалось ограничить доступ к {}: {error}", path.display()))
}

fn program(name: &str) -> Result<PathBuf, String> {
    env::split_paths(&env::var_os("PATH").unwrap_or_default())
        .map(|directory| directory.join(name))
        .find(|path| path.is_file())
        .ok_or_else(|| {
            format!("Не найдена системная программа {name}. Установите PostgreSQL и Xvfb")
        })
}

fn free_port() -> Result<u16, String> {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|socket| socket.local_addr())
        .map(|address| address.port())
        .map_err(|error| format!("Не удалось выбрать локальный порт: {error}"))
}

fn log_file(state_dir: &Path, name: &str) -> Result<Stdio, String> {
    let path = state_dir.join(name);
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map(Stdio::from)
        .map_err(|error| format!("Не удалось открыть {}: {error}", path.display()))
}

fn spawn_logged(
    command: &mut Command,
    state_dir: &Path,
    name: &str,
) -> Result<ManagedChild, String> {
    // These processes are started by a short-lived spawn_blocking thread.
    // PR_SET_PDEATHSIG would terminate them when that thread finishes, even
    // while the Tauri process and its native services are still running.
    command
        .stdout(log_file(state_dir, name)?)
        .stderr(log_file(state_dir, name)?)
        .spawn()
        .map(ManagedChild)
        .map_err(|error| {
            format!(
                "Не удалось запустить {}: {error}",
                command.get_program().to_string_lossy()
            )
        })
}

fn run_checked(command: &mut Command, action: &str) -> Result<std::process::Output, String> {
    let output = command
        .output()
        .map_err(|error| format!("{action}: {error}"))?;
    if output.status.success() {
        Ok(output)
    } else {
        Err(format!(
            "{action}: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        ))
    }
}

fn wait_for_child<F>(
    child: &mut ManagedChild,
    timeout: Duration,
    mut ready: F,
    log: &Path,
) -> Result<(), String>
where
    F: FnMut() -> bool,
{
    let deadline = Instant::now() + timeout;
    loop {
        if ready() {
            return Ok(());
        }
        if let Ok(Some(status)) = child.0.try_wait() {
            return Err(format!(
                "Служба завершилась с кодом {status}. Проверьте {}",
                log.display()
            ));
        }
        if Instant::now() >= deadline {
            return Err(format!(
                "Служба не стала доступна. Проверьте {}",
                log.display()
            ));
        }
        thread::sleep(Duration::from_millis(150));
    }
}

fn api_ready(port: u16, token: &str) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(250)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request = format!("GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Price-Watch-Token: {token}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut response = [0u8; 256];
    matches!(stream.read(&mut response), Ok(count) if response[..count].starts_with(b"HTTP/1.1 200"))
}

fn random_token() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    File::open("/dev/urandom")
        .and_then(|mut source| source.read_exact(&mut bytes))
        .map_err(|error| format!("Не удалось создать секрет API: {error}"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

fn pg_major(text: &str) -> Option<&str> {
    text.split_whitespace().find_map(|word| {
        let number = word.trim_start_matches('v');
        if number.chars().next()?.is_ascii_digit() {
            Some(number.split('.').next().unwrap_or(number))
        } else {
            None
        }
    })
}

fn encoded_query_value(value: &str) -> String {
    let mut encoded = String::new();
    for byte in value.as_bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b'~' | b'/') {
            encoded.push(*byte as char);
        } else {
            encoded.push_str(&format!("%{byte:02X}"));
        }
    }
    encoded
}

impl NativeServices {
    pub fn start(project_root: &Path, data_dir: &Path, state_dir: &Path) -> Result<Self, String> {
        let initdb = program("initdb")?;
        let postgres_bin = program("postgres")?;
        let psql = program("psql")?;
        let createdb = program("createdb")?;
        let pg_isready = program("pg_isready")?;
        let pg_dump = program("pg_dump")?;
        let xvfb = program("Xvfb")?;
        let xauth = program("xauth")?;
        let python = if project_root.join(".venv/bin/python").is_file() {
            project_root.join(".venv/bin/python")
        } else {
            program("python3")?
        };
        if !project_root.join("main.py").is_file() {
            return Err(format!(
                "Не найден код приложения в {}",
                project_root.display()
            ));
        }

        private_dir(data_dir)?;
        private_dir(state_dir)?;
        let lock = OpenOptions::new()
            .create(true)
            .write(true)
            .open(state_dir.join("native.lock"))
            .map_err(|error| format!("Не удалось открыть блокировку приложения: {error}"))?;
        if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err("Нативные службы уже используются другим окном Price Watch".to_string());
        }

        let pg_data = data_dir.join("postgres");
        if !pg_data.join("PG_VERSION").exists() {
            run_checked(
                Command::new(&initdb)
                    .arg("-D")
                    .arg(&pg_data)
                    .arg("--auth-local=trust"),
                "Инициализация локального PostgreSQL",
            )?;
        }
        let data_version = fs::read_to_string(pg_data.join("PG_VERSION"))
            .map_err(|error| format!("Не удалось прочитать версию базы: {error}"))?;
        let binary_version = run_checked(
            Command::new(&postgres_bin).arg("--version"),
            "Версия PostgreSQL",
        )?;
        if pg_major(&String::from_utf8_lossy(&binary_version.stdout)) != pg_major(&data_version) {
            return Err(format!(
                "Версия данных PostgreSQL ({}) не совпадает с установленной программой ({}). Сделайте резервную копию и обновите кластер PostgreSQL",
                data_version.trim(), String::from_utf8_lossy(&binary_version.stdout).trim()
            ));
        }

        let runtime_base = env::var_os("XDG_RUNTIME_DIR")
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
            .unwrap_or_else(|| state_dir.to_path_buf());
        let socket_dir = runtime_base.join("price-watch");
        private_dir(&socket_dir)?;
        if socket_dir.as_os_str().len() > 80 {
            return Err("Путь к сокету PostgreSQL слишком длинный".to_string());
        }
        let pg_port = free_port()?;
        let mut postgres = spawn_logged(
            Command::new(&postgres_bin)
                .arg("-D")
                .arg(&pg_data)
                .arg("-c")
                .arg("listen_addresses=")
                .arg("-c")
                .arg(format!("unix_socket_directories={}", socket_dir.display()))
                .arg("-p")
                .arg(pg_port.to_string()),
            state_dir,
            "postgres.log",
        )?;
        wait_for_child(
            &mut postgres,
            Duration::from_secs(30),
            || {
                Command::new(&pg_isready)
                    .arg("-h")
                    .arg(&socket_dir)
                    .arg("-p")
                    .arg(pg_port.to_string())
                    .status()
                    .is_ok_and(|status| status.success())
            },
            &state_dir.join("postgres.log"),
        )?;

        let db_exists = run_checked(
            Command::new(&psql)
                .arg("-h")
                .arg(&socket_dir)
                .arg("-p")
                .arg(pg_port.to_string())
                .arg("-d")
                .arg("postgres")
                .arg("-tAc")
                .arg("SELECT 1 FROM pg_database WHERE datname = 'price_watch'"),
            "Проверка локальной базы",
        )?;
        if String::from_utf8_lossy(&db_exists.stdout).trim() != "1" {
            run_checked(
                Command::new(&createdb)
                    .arg("-h")
                    .arg(&socket_dir)
                    .arg("-p")
                    .arg(pg_port.to_string())
                    .arg("price_watch"),
                "Создание локальной базы",
            )?;
        }
        let backup_dir = data_dir.join("backups");
        backup_database(&pg_dump, &socket_dir, pg_port, &backup_dir)?;
        let socket_path = socket_dir
            .to_str()
            .ok_or("Путь к сокету PostgreSQL должен быть UTF-8")?;
        let database_url = format!(
            "postgresql:///price_watch?host={}&port={pg_port}",
            encoded_query_value(socket_path)
        );

        let display_number = (90..200)
            .find(|number| {
                !Path::new(&format!("/tmp/.X11-unix/X{number}")).exists()
                    && !Path::new(&format!("/tmp/.X{number}-lock")).exists()
            })
            .ok_or("Нет свободного номера скрытого дисплея")?;
        let xauthority = socket_dir.join("Xauthority");
        OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&xauthority)
            .map_err(|error| format!("Не удалось создать файл доступа Xvfb: {error}"))?;
        fs::set_permissions(&xauthority, fs::Permissions::from_mode(0o600))
            .map_err(|error| format!("Не удалось ограничить доступ к Xvfb: {error}"))?;
        run_checked(
            Command::new(&xauth)
                .arg("-f")
                .arg(&xauthority)
                .arg("add")
                .arg(format!(":{display_number}"))
                .arg("MIT-MAGIC-COOKIE-1")
                .arg(random_token()?),
            "Создание доступа к скрытому дисплею",
        )?;
        let mut display = spawn_logged(
            Command::new(&xvfb)
                .arg(format!(":{display_number}"))
                .args(["-screen", "0", "1920x1080x24", "-nolisten", "tcp"])
                .arg("-auth")
                .arg(&xauthority),
            state_dir,
            "xvfb.log",
        )?;
        wait_for_child(
            &mut display,
            Duration::from_secs(15),
            || {
                std::os::unix::net::UnixStream::connect(format!("/tmp/.X11-unix/X{display_number}"))
                    .is_ok()
            },
            &state_dir.join("xvfb.log"),
        )?;

        let api_port = free_port()?;
        let api_token = random_token()?;
        let mut api = spawn_logged(
            Command::new(python)
                .arg("main.py")
                .arg("api")
                .arg("--host")
                .arg("127.0.0.1")
                .arg("--port")
                .arg(api_port.to_string())
                .current_dir(project_root)
                .env("DATABASE_URL", &database_url)
                .env("PRICE_WATCH_API_TOKEN", &api_token),
            state_dir,
            "api.log",
        )?;
        wait_for_child(
            &mut api,
            Duration::from_secs(60),
            || api_ready(api_port, &api_token),
            &state_dir.join("api.log"),
        )?;

        Ok(Self {
            _lock: lock,
            api,
            display,
            postgres,
            database_url,
            api_port,
            api_token,
            display_number,
            xauthority,
            pg_dump,
            socket_dir,
            pg_port,
            backup_dir,
        })
    }

    fn backup_database(&self) -> Result<(), String> {
        backup_database(
            &self.pg_dump,
            &self.socket_dir,
            self.pg_port,
            &self.backup_dir,
        )
    }

    pub fn is_ready(&mut self) -> bool {
        self.api.0.try_wait().is_ok_and(|status| status.is_none())
            && self
                .postgres
                .0
                .try_wait()
                .is_ok_and(|status| status.is_none())
            && self
                .display
                .0
                .try_wait()
                .is_ok_and(|status| status.is_none())
            && api_ready(self.api_port, &self.api_token)
    }
}

fn backup_database(
    pg_dump: &Path,
    socket_dir: &Path,
    port: u16,
    backup_dir: &Path,
) -> Result<(), String> {
    private_dir(backup_dir)?;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_millis();
    let path = backup_dir.join(format!("native-{stamp}.dump"));
    let partial = backup_dir.join(format!("native-{stamp}.partial"));
    let file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .mode(0o600)
        .open(&partial)
        .map_err(|error| {
            format!(
                "Не удалось создать резервную копию {}: {error}",
                partial.display()
            )
        })?;
    let result = Command::new(pg_dump)
        .arg("-Fc")
        .arg("-h")
        .arg(socket_dir)
        .arg("-p")
        .arg(port.to_string())
        .arg("-d")
        .arg("price_watch")
        .stdout(Stdio::from(file))
        .output()
        .map_err(|error| format!("Не удалось запустить pg_dump: {error}"));
    match result {
        Ok(output) if output.status.success() => {
            fs::rename(&partial, &path)
                .map_err(|error| format!("Не удалось сохранить резервную копию: {error}"))?;
        }
        Ok(output) => {
            let _ = fs::remove_file(&partial);
            return Err(format!(
                "pg_dump завершился с ошибкой: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ));
        }
        Err(error) => {
            let _ = fs::remove_file(&partial);
            return Err(error);
        }
    }
    let mut backups: Vec<PathBuf> = fs::read_dir(backup_dir)
        .map_err(|error| error.to_string())?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|entry| {
            entry.file_name().is_some_and(|name| {
                let name = name.to_string_lossy();
                name.starts_with("native-") && name.ends_with(".dump")
            })
        })
        .collect();
    backups.sort();
    let remove_count = backups.len().saturating_sub(10);
    for old in backups.into_iter().take(remove_count) {
        fs::remove_file(&old).map_err(|error| {
            format!("Не удалось удалить старую копию {}: {error}", old.display())
        })?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{encoded_query_value, pg_major, spawn_logged, NativeServices};

    #[test]
    fn service_outlives_the_thread_that_starts_it() {
        let state = std::env::temp_dir().join(format!(
            "price-watch-child-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir(&state).unwrap();
        let child = std::thread::spawn({
            let state = state.clone();
            move || {
                spawn_logged(
                    std::process::Command::new("sleep").arg("20"),
                    &state,
                    "child.log",
                )
            }
        })
        .join()
        .unwrap()
        .unwrap();
        let mut child = child;
        assert!(child.0.try_wait().unwrap().is_none());
        drop(child);
        std::fs::remove_dir_all(state).unwrap();
    }

    #[test]
    fn compares_postgres_major_versions() {
        assert_eq!(pg_major("postgres (PostgreSQL) 18.2"), Some("18"));
        assert_eq!(pg_major("18\n"), Some("18"));
    }

    #[test]
    fn encodes_socket_path_for_database_url() {
        assert_eq!(
            encoded_query_value("/home/user name/price&watch"),
            "/home/user%20name/price%26watch"
        );
    }

    #[test]
    #[ignore = "requires PostgreSQL, Xvfb, xauth, Python dependencies and a private test root"]
    fn starts_native_services_in_private_directories() {
        let root = std::path::PathBuf::from(
            std::env::var("PRICE_WATCH_NATIVE_SMOKE_ROOT")
                .expect("set PRICE_WATCH_NATIVE_SMOKE_ROOT"),
        );
        let mut services = NativeServices::start(
            &root.join("project"),
            &root.join("smoke-data"),
            &root.join("smoke-state"),
        )
        .expect("native services should start");
        assert!(services.is_ready());
        assert!(root
            .join("smoke-data/backups")
            .read_dir()
            .unwrap()
            .next()
            .is_some());
    }
}
