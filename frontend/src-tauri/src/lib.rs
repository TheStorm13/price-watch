use serde::Serialize;
use std::{
    env,
    fs::{self, OpenOptions},
    net::{SocketAddr, TcpStream},
    os::unix::fs::PermissionsExt,
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

mod native_services;
use native_services::NativeServices;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ApiConfig {
    base_url: String,
    token: Option<String>,
}

struct RuntimeState {
    project_root: PathBuf,
    profile_dir: PathBuf,
    state_dir: PathBuf,
    data_dir: PathBuf,
    config_dir: PathBuf,
    native: Mutex<Option<NativeServices>>,
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
    fn ensure_services(&self) -> Result<ApiConfig, String> {
        let _startup_guard = self
            .startup
            .lock()
            .map_err(|_| "Ошибка блокировки запуска")?;

        self.prepare_user_paths()?;
        self.load_desktop_env();
        self.prepare_worker_log()?;
        self.ensure_native_services()
    }

    fn ensure_native_services(&self) -> Result<ApiConfig, String> {
        let mut native = self.native.lock().map_err(|_| "Ошибка состояния служб")?;
        if native.as_mut().is_some_and(|services| !services.is_ready()) {
            self.stop_worker();
            *native = None;
        }
        if native.is_none() {
            *native = Some(NativeServices::start(
                &self.project_root,
                &self.data_dir,
                &self.state_dir,
            )?);
        }
        let services = native.as_ref().ok_or("Нативные службы не запущены")?;
        let database_url = services.database_url.clone();
        let display_number = services.display_number;
        let xauthority = services.xauthority.clone();
        let config = ApiConfig {
            base_url: format!("http://127.0.0.1:{}", services.api_port),
            token: Some(services.api_token.clone()),
        };
        drop(native);
        if !self.worker_is_running()? {
            self.start_worker(database_url, display_number, Some(xauthority))?;
        }
        Ok(config)
    }

    fn start_worker(
        &self,
        database_url: String,
        display_number: u16,
        xauthority: Option<PathBuf>,
    ) -> Result<(), String> {
        let venv_python = self.project_root.join(".venv/bin/python");
        let python = if venv_python.is_file() {
            venv_python
        } else {
            PathBuf::from("python3")
        };

        let log_path = self.state_dir.join("desktop-worker.log");
        let stdout = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .map_err(|error| format!("Не удалось открыть {}: {error}", log_path.display()))?;
        let stderr = stdout
            .try_clone()
            .map_err(|error| format!("Не удалось открыть stderr worker: {error}"))?;
        let project_root = self.project_root.clone();
        let profile_dir = self.profile_dir.clone();
        let display = format!(":{display_number}");
        let running = Arc::new(AtomicBool::new(false));
        let supervisor_running = Arc::clone(&running);
        let (startup_tx, startup_rx) = mpsc::sync_channel(1);
        let (stop_tx, stop_rx) = mpsc::channel();

        let supervisor = thread::spawn(move || {
            let mut command = Command::new(python);
            command
                .args(["main.py", "worker", "--profile-dir"])
                .arg(profile_dir)
                .args([
                    "--browser-channel",
                    "chrome",
                    "--chrome-platform",
                    "x11",
                    "--virtual-display",
                ])
                .current_dir(project_root)
                .env("DATABASE_URL", database_url)
                .env("DISPLAY", display)
                .stdout(Stdio::from(stdout))
                .stderr(Stdio::from(stderr));
            if let Some(auth) = xauthority {
                command.env("XAUTHORITY", auth);
            }

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
        fs::create_dir_all(&self.state_dir)
            .map_err(|error| format!("Не удалось создать каталог логов: {error}"))?;
        let path = self.state_dir.join("desktop-worker.log");
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
        self.prepare_user_paths()?;
        let store_urls = [
            "https://www.ozon.ru/",
            "https://www.wildberries.ru/",
            "https://aliexpress.ru/",
        ];
        let profile = self.profile_dir.clone();
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
        self.prepare_user_paths()?;
        self.stop_manual_browser();
        if active_debug_port(&self.profile_dir).is_some() {
            return Err("Не удалось закрыть Chrome приложения перед сбором цен".to_string());
        }
        Ok(())
    }

    fn prepare_user_paths(&self) -> Result<(), String> {
        migrate_profile(
            &self.project_root.join(".playwright-profile"),
            &self.profile_dir,
        )?;
        fs::create_dir_all(&self.profile_dir)
            .map_err(|error| format!("Не удалось создать профиль Chrome: {error}"))?;
        fs::set_permissions(&self.profile_dir, fs::Permissions::from_mode(0o700))
            .map_err(|error| format!("Не удалось ограничить доступ к профилю Chrome: {error}"))?;
        fs::create_dir_all(&self.state_dir)
            .map_err(|error| format!("Не удалось создать каталог состояния: {error}"))?;
        fs::set_permissions(&self.state_dir, fs::Permissions::from_mode(0o700))
            .map_err(|error| format!("Не удалось ограничить доступ к логам: {error}"))
    }

    fn load_desktop_env(&self) {
        dotenvy::from_path(self.config_dir.join("config.env")).ok();
        dotenvy::from_path(self.project_root.join(".env")).ok();
    }
}

fn migrate_profile(old: &Path, new: &Path) -> Result<(), String> {
    if !old.exists() {
        return Ok(());
    }
    if new.exists() {
        return Err(format!(
            "Найдены два профиля Chrome: {} и {}. Выберите нужный профиль и удалите или перенесите второй",
            old.display(),
            new.display()
        ));
    }
    if active_debug_port(old).is_some() {
        return Err(
            "Закройте Chrome приложения для переноса профиля и повторите запуск".to_string(),
        );
    }
    if let Some(parent) = new.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Не удалось создать каталог профиля Chrome: {error}"))?;
    }
    fs::rename(old, new).map_err(|error| {
        format!(
            "Не удалось перенести профиль Chrome из {} в {}: {error}",
            old.display(),
            new.display()
        )
    })
}

#[cfg(test)]
mod path_tests {
    use super::{migrate_profile, RuntimeState};
    use std::{
        fs,
        path::PathBuf,
        sync::Mutex,
        time::{SystemTime, UNIX_EPOCH},
    };

    #[test]
    fn moves_existing_browser_profile_without_losing_data() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "price-watch-profile-test-{}-{unique}",
            std::process::id()
        ));
        let old = root.join("project/.playwright-profile");
        let new = root.join("data/price-watch/chrome-profile");
        fs::create_dir_all(&old).unwrap();
        fs::write(old.join("Cookies"), b"saved session").unwrap();

        migrate_profile(&old, &new).unwrap();

        assert!(!old.exists());
        assert_eq!(fs::read(new.join("Cookies")).unwrap(), b"saved session");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    #[ignore = "requires PostgreSQL, Xvfb, xauth, Python dependencies and a private test root"]
    fn starts_native_worker_without_opening_chrome() {
        let root = PathBuf::from(
            std::env::var("PRICE_WATCH_NATIVE_SMOKE_ROOT")
                .expect("set PRICE_WATCH_NATIVE_SMOKE_ROOT"),
        );
        let runtime = RuntimeState {
            project_root: root.join("project"),
            profile_dir: root.join("full-data/chrome-profile"),
            data_dir: root.join("full-data"),
            state_dir: root.join("full-state"),
            config_dir: root.join("full-config"),
            native: Mutex::new(None),
            worker: Mutex::new(None),
            manual_browser: Mutex::new(None),
            startup: Mutex::new(()),
        };
        let config = runtime
            .ensure_services()
            .expect("native runtime should start");
        assert!(config.token.is_some());
        std::thread::sleep(std::time::Duration::from_millis(750));
        assert!(runtime.worker_is_running().unwrap());
        assert!(runtime.native.lock().unwrap().as_mut().unwrap().is_ready());
        assert!(!runtime.profile_dir.join("DevToolsActivePort").exists());
        runtime.stop_worker();
        *runtime.native.lock().unwrap() = None;
    }
}

fn active_debug_port(profile: &Path) -> Option<u16> {
    let content = fs::read_to_string(profile.join("DevToolsActivePort")).ok()?;
    let port = content.lines().next()?.parse::<u16>().ok()?;
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    TcpStream::connect_timeout(&address, Duration::from_millis(300)).ok()?;
    Some(port)
}

fn project_root() -> PathBuf {
    env::var_os("PRICE_ANALYZER_PROJECT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let installed = PathBuf::from("/usr/lib/price-watch");
            let installed_binary = env::current_exe()
                .ok()
                .and_then(|path| path.parent().map(Path::to_path_buf))
                .is_some_and(|directory| directory == Path::new("/usr/bin"));
            if installed_binary && installed.join("main.py").is_file() {
                return installed;
            }
            let development = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
            if development.join("main.py").is_file() {
                return development;
            }
            if installed.join("main.py").is_file() {
                installed
            } else {
                development
            }
        })
}

fn user_base_dir(variable: &str, fallback: &str) -> Result<PathBuf, String> {
    if let Some(value) = env::var_os(variable) {
        let path = PathBuf::from(value);
        if path.is_absolute() {
            return Ok(path);
        }
    }
    let home = env::var_os("HOME")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or("Не найден домашний каталог пользователя")?;
    Ok(home.join(fallback))
}

#[tauri::command]
async fn ensure_services(state: tauri::State<'_, Arc<RuntimeState>>) -> Result<ApiConfig, String> {
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
        profile_dir: user_base_dir("XDG_DATA_HOME", ".local/share")
            .expect("Не удалось определить каталог данных пользователя")
            .join("price-watch/chrome-profile"),
        state_dir: user_base_dir("XDG_STATE_HOME", ".local/state")
            .expect("Не удалось определить каталог состояния пользователя")
            .join("price-watch"),
        data_dir: user_base_dir("XDG_DATA_HOME", ".local/share")
            .expect("Не удалось определить каталог данных пользователя")
            .join("price-watch"),
        config_dir: user_base_dir("XDG_CONFIG_HOME", ".config")
            .expect("Не удалось определить каталог конфигурации пользователя")
            .join("price-watch"),
        native: Mutex::new(None),
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
            if let Ok(mut native) = cleanup.native.lock() {
                *native = None;
            }
        }
    });
}
