use std::{
    env,
    fs::{self, OpenOptions},
    net::{SocketAddr, TcpStream},
    os::unix::net::UnixStream,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, Mutex,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};
use tauri_plugin_dialog::DialogExt;

struct RuntimeState {
    project_root: PathBuf,
    worker: Mutex<Option<WorkerProcess>>,
    manual_browser: Mutex<Option<Child>>,
    startup: Mutex<()>,
}

struct WorkerProcess {
    running: Arc<AtomicBool>,
    stop: mpsc::Sender<()>,
    supervisor: JoinHandle<()>,
}

impl RuntimeState {
    fn ensure_services(&self) -> Result<(), String> {
        let _startup_guard = self
            .startup
            .lock()
            .map_err(|_| "Ошибка блокировки запуска")?;

        if self.worker_is_running()? && api_is_ready() {
            return Ok(());
        }

        dotenvy::from_path(self.project_root.join(".env")).ok();
        self.prepare_worker_log()?;
        self.stop_container_browser_services()?;
        self.start_backend()?;
        wait_for_api(Duration::from_secs(120))?;
        wait_for_desktop_display(Duration::from_secs(30))?;
        self.start_worker()?;
        Ok(())
    }

    fn stop_container_browser_services(&self) -> Result<(), String> {
        let status = Command::new("docker")
            .args(["compose", "stop", "worker", "frontend"])
            .current_dir(&self.project_root)
            .status()
            .map_err(|error| format!("Не удалось запустить Docker Compose: {error}"))?;
        if status.success() {
            Ok(())
        } else {
            Err(format!("Docker Compose завершился с кодом {status}"))
        }
    }

    fn start_backend(&self) -> Result<(), String> {
        let mut arguments = vec!["compose", "up"];
        if cfg!(debug_assertions) {
            arguments.push("--build");
        }
        arguments.extend([
            "-d",
            "db",
            "migrate",
            "api",
            "logs",
            "desktop-worker-logs",
            "desktop-display",
        ]);
        let status = Command::new("docker")
            .args(arguments)
            .current_dir(&self.project_root)
            .status()
            .map_err(|error| format!("Не удалось поднять backend: {error}"))?;
        if status.success() {
            Ok(())
        } else {
            Err(format!(
                "Сборка или запуск backend завершились с кодом {status}"
            ))
        }
    }

    fn start_worker(&self) -> Result<(), String> {
        let python = self.project_root.join(".venv/bin/python");
        if !python.is_file() {
            return Err(format!(
                "Не найден Python worker: {}. Создайте .venv и установите requirements.txt",
                python.display()
            ));
        }

        let log_path = self.project_root.join("output/desktop-worker.log");
        let stdout = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|error| format!("Не удалось открыть {}: {error}", log_path.display()))?;
        let stderr = stdout
            .try_clone()
            .map_err(|error| format!("Не удалось открыть stderr worker: {error}"))?;
        let database_url = env::var("DATABASE_URL").unwrap_or_else(|_| {
            "postgresql://price_analyzer:price_analyzer@127.0.0.1:5432/price_analyzer".to_string()
        });

        let project_root = self.project_root.clone();
        let running = Arc::new(AtomicBool::new(false));
        let supervisor_running = Arc::clone(&running);
        let (startup_tx, startup_rx) = mpsc::sync_channel(1);
        let (stop_tx, stop_rx) = mpsc::channel();

        let supervisor = thread::spawn(move || {
            let mut command = Command::new(python);
            command
                .args([
                    "main.py",
                    "worker",
                    "--profile-dir",
                    ".playwright-profile",
                    "--browser-channel",
                    "chrome",
                    "--chrome-platform",
                    "x11",
                    "--virtual-display",
                ])
                .current_dir(project_root)
                .env("DATABASE_URL", database_url)
                .env("DISPLAY", ":98")
                .stdout(Stdio::from(stdout))
                .stderr(Stdio::from(stderr));

            #[cfg(target_os = "linux")]
            {
                use std::os::unix::process::CommandExt;

                // The supervisor lives for as long as its child. If Tauri dies,
                // Linux terminates this thread and then the Python worker.
                unsafe {
                    command.pre_exec(|| {
                        if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGTERM) == -1 {
                            return Err(std::io::Error::last_os_error());
                        }
                        Ok(())
                    });
                }
            }

            let mut child = match command.spawn() {
                Ok(child) => child,
                Err(error) => {
                    let _ = startup_tx.send(Err(format!("Не удалось запустить worker: {error}")));
                    return;
                }
            };
            supervisor_running.store(true, Ordering::Release);
            let _ = startup_tx.send(Ok(()));

            loop {
                if stop_rx.try_recv().is_ok() {
                    let _ = child.kill();
                    let _ = child.wait();
                    break;
                }
                match child.try_wait() {
                    Ok(Some(_)) | Err(_) => break,
                    Ok(None) => thread::sleep(Duration::from_millis(200)),
                }
            }
            supervisor_running.store(false, Ordering::Release);
        });

        startup_rx
            .recv_timeout(Duration::from_secs(5))
            .map_err(|_| "Worker не сообщил о запуске за 5 секунд".to_string())??;
        *self.worker.lock().map_err(|_| "Ошибка состояния worker")? = Some(WorkerProcess {
            running,
            stop: stop_tx,
            supervisor,
        });
        Ok(())
    }

    fn prepare_worker_log(&self) -> Result<(), String> {
        fs::create_dir_all(self.project_root.join("output"))
            .map_err(|error| format!("Не удалось создать каталог логов: {error}"))?;
        let path = self.project_root.join("output/desktop-worker.log");
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .map(|_| ())
            .map_err(|error| format!("Не удалось подготовить {}: {error}", path.display()))
    }

    fn worker_is_running(&self) -> Result<bool, String> {
        let mut worker = self.worker.lock().map_err(|_| "Ошибка состояния worker")?;
        let Some(process) = worker.as_ref() else {
            return Ok(false);
        };
        if process.running.load(Ordering::Acquire) {
            return Ok(true);
        }
        if let Some(process) = worker.take() {
            let _ = process.supervisor.join();
        }
        Ok(false)
    }

    fn stop_worker(&self) {
        if let Ok(mut worker) = self.worker.lock() {
            if let Some(process) = worker.take() {
                let _ = process.stop.send(());
                let _ = process.supervisor.join();
            }
        }
    }

    fn open_store_browser(&self) -> Result<(), String> {
        let store_urls = [
            "https://www.ozon.ru/",
            "https://www.wildberries.ru/",
            "https://aliexpress.ru/",
        ];
        let profile = self.project_root.join(".playwright-profile");
        fs::create_dir_all(&profile)
            .map_err(|error| format!("Не удалось создать профиль Chrome: {error}"))?;
        let mut browser = self
            .manual_browser
            .lock()
            .map_err(|_| "Ошибка состояния Chrome")?;
        let running = match browser.as_mut() {
            Some(child) => child
                .try_wait()
                .map_err(|error| format!("Не удалось проверить Chrome: {error}"))?
                .is_none(),
            None => false,
        };
        let existing_port = active_debug_port(&profile);
        if !running && existing_port.is_some() {
            return Err(
                "Chrome занят сбором. Дождитесь завершения запуска и повторите попытку."
                    .to_string(),
            );
        }
        if running && existing_port.is_none() {
            return Err("Chrome приложения не открыл порт управления".to_string());
        }
        if !running {
            *browser = None;
        }

        let executable = env::var_os("CHROME_BINARY")
            .map(PathBuf::from)
            .or_else(|| {
                ["google-chrome-stable", "google-chrome"]
                    .iter()
                    .find_map(|name| {
                        env::split_paths(&env::var_os("PATH")?)
                            .map(|path| path.join(name))
                            .find(|path| path.is_file())
                    })
            })
            .ok_or("Не найден установленный Google Chrome")?;
        let log_path = profile.join("chrome.log");
        let stdout = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|error| format!("Не удалось открыть лог Chrome: {error}"))?;
        let stderr = stdout
            .try_clone()
            .map_err(|error| format!("Не удалось открыть лог Chrome: {error}"))?;
        let mut child = Command::new(executable)
            .arg("--remote-debugging-port=0")
            .arg("--remote-debugging-address=127.0.0.1")
            .arg(format!("--user-data-dir={}", profile.display()))
            .args([
                "--no-first-run",
                "--no-default-browser-check",
                "--ozone-platform=x11",
            ])
            .args(store_urls)
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr))
            .spawn()
            .map_err(|error| format!("Не удалось открыть Chrome: {error}"))?;
        if existing_port.is_none() {
            let deadline = Instant::now() + Duration::from_secs(10);
            while active_debug_port(&profile).is_none() {
                if let Some(status) = child
                    .try_wait()
                    .map_err(|error| format!("Не удалось проверить Chrome: {error}"))?
                {
                    return Err(format!(
                        "Chrome завершился с кодом {status}. Проверьте {}",
                        log_path.display()
                    ));
                }
                if Instant::now() >= deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err(format!(
                        "Chrome не открыл порт управления. Проверьте {}",
                        log_path.display()
                    ));
                }
                thread::sleep(Duration::from_millis(100));
            }
            *browser = Some(child);
        } else {
            thread::spawn(move || {
                let _ = child.wait();
            });
        }
        Ok(())
    }

    fn stop_manual_browser(&self) {
        if let Ok(mut browser) = self.manual_browser.lock() {
            if let Some(mut child) = browser.take() {
                #[cfg(target_os = "linux")]
                unsafe {
                    libc::kill(child.id() as i32, libc::SIGTERM);
                }
                let deadline = Instant::now() + Duration::from_secs(3);
                while matches!(child.try_wait(), Ok(None)) && Instant::now() < deadline {
                    thread::sleep(Duration::from_millis(100));
                }
                if matches!(child.try_wait(), Ok(None)) {
                    let _ = child.kill();
                }
                let _ = child.wait();
            }
        }
    }

    fn prepare_collection(&self) -> Result<(), String> {
        self.stop_manual_browser();
        if active_debug_port(&self.project_root.join(".playwright-profile")).is_some() {
            return Err("Не удалось закрыть Chrome приложения перед сбором цен".to_string());
        }
        Ok(())
    }
}

fn active_debug_port(profile: &Path) -> Option<u16> {
    let content = fs::read_to_string(profile.join("DevToolsActivePort")).ok()?;
    let port = content.lines().next()?.parse::<u16>().ok()?;
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    TcpStream::connect_timeout(&address, Duration::from_millis(300)).ok()?;
    Some(port)
}

fn api_is_ready() -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], 8000));
    TcpStream::connect_timeout(&address, Duration::from_millis(300)).is_ok()
}

fn wait_for_desktop_display(timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if UnixStream::connect("/tmp/.X11-unix/X98").is_ok() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(200));
    }
    Err("Скрытый дисплей Chrome не стал доступен за 30 секунд".to_string())
}

fn wait_for_api(timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if api_is_ready() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(500));
    }
    Err("API не стал доступен на 127.0.0.1:8000 за 120 секунд".to_string())
}

fn project_root() -> PathBuf {
    env::var_os("PRICE_ANALYZER_PROJECT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."))
}

#[tauri::command]
async fn ensure_services(state: tauri::State<'_, Arc<RuntimeState>>) -> Result<(), String> {
    let state = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || state.ensure_services())
        .await
        .map_err(|error| format!("Ошибка задачи запуска: {error}"))?
}

#[tauri::command]
async fn open_store_browser(state: tauri::State<'_, Arc<RuntimeState>>) -> Result<(), String> {
    let state = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || state.open_store_browser())
        .await
        .map_err(|error| format!("Ошибка запуска Chrome: {error}"))?
}

#[tauri::command]
async fn prepare_collection(state: tauri::State<'_, Arc<RuntimeState>>) -> Result<(), String> {
    let state = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || state.prepare_collection())
        .await
        .map_err(|error| format!("Ошибка подготовки сбора: {error}"))?
}

#[tauri::command]
async fn save_export_file(
    app: tauri::AppHandle,
    contents: String,
    file_name: String,
) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let selected = app
            .dialog()
            .file()
            .set_title("Экспорт карточек и истории")
            .set_file_name(file_name)
            .add_filter("JSON", &["json"])
            .blocking_save_file();
        let Some(path) = selected else {
            return Ok(false);
        };
        let path = path.into_path().map_err(|error| error.to_string())?;
        fs::write(path, contents).map_err(|error| format!("Не удалось сохранить файл: {error}"))?;
        Ok(true)
    })
    .await
    .map_err(|error| format!("Ошибка выбора файла: {error}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let runtime = Arc::new(RuntimeState {
        project_root: project_root(),
        worker: Mutex::new(None),
        manual_browser: Mutex::new(None),
        startup: Mutex::new(()),
    });
    let cleanup = Arc::clone(&runtime);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(runtime)
        .invoke_handler(tauri::generate_handler![
            ensure_services,
            open_store_browser,
            prepare_collection,
            save_export_file
        ])
        .build(tauri::generate_context!())
        .expect("Не удалось собрать Tauri-приложение");

    app.run(move |_app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            cleanup.stop_worker();
            cleanup.stop_manual_browser();
        }
    });
}
