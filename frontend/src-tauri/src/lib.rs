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
use tauri::{Emitter, Manager};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_dialog::DialogExt;

mod native_services;
mod process_log;
use native_services::NativeServices;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ApiConfig {
    base_url: String,
    token: Option<String>,
}

impl PartialEq for ApiConfig {
    fn eq(&self, other: &Self) -> bool {
        self.base_url == other.base_url && self.token == other.token
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BackgroundState {
    enabled: bool,
    service_error: Option<String>,
}

enum ServiceEvent<'a> {
    Changed(&'a ApiConfig),
    Error(&'a str),
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
    manual_browser_log: Mutex<Option<process_log::LogDrain>>,
    startup: Mutex<()>,
    last_config: Mutex<Option<ApiConfig>>,
    service_error: Mutex<Option<String>>,
}

struct WorkerProcess {
    running: Arc<AtomicBool>,
    stop: mpsc::Sender<()>,
    supervisor: JoinHandle<()>,
}

fn wait_for_worker_exit(child: &mut Child, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while matches!(child.try_wait(), Ok(None)) && Instant::now() < deadline {
        thread::sleep(Duration::from_millis(50));
    }
    matches!(child.try_wait(), Ok(Some(_)))
}

fn stop_child_gracefully(child: &mut Child, interrupt_timeout: Duration, term_timeout: Duration) {
    if matches!(child.try_wait(), Ok(Some(_))) {
        return;
    }
    // asyncio.run handles SIGINT by cancelling the active task, which lets
    // CollectionService and the Ozon context manager close their resources.
    #[cfg(unix)]
    unsafe {
        libc::kill(child.id() as i32, libc::SIGINT);
    }
    if !wait_for_worker_exit(child, interrupt_timeout) {
        #[cfg(unix)]
        unsafe {
            libc::kill(child.id() as i32, libc::SIGTERM);
        }
        if !wait_for_worker_exit(child, term_timeout) {
            let _ = child.kill();
        }
    }
    let _ = child.wait();
}

impl RuntimeState {
    fn python_executable(&self) -> PathBuf {
        let venv_python = self.project_root.join(".venv/bin/python");
        if venv_python.is_file() {
            venv_python
        } else {
            PathBuf::from("python3")
        }
    }

    fn ensure_and_publish(&self, app: &tauri::AppHandle) -> Result<ApiConfig, String> {
        let result = self.ensure_services();
        self.record_service_result(&result, |event| match event {
            ServiceEvent::Changed(config) => {
                let _ = app.emit("services-changed", config);
            }
            ServiceEvent::Error(message) => {
                let _ = app.emit("services-error", message);
            }
        });
        result
    }

    fn record_service_result(
        &self,
        result: &Result<ApiConfig, String>,
        mut publish: impl FnMut(ServiceEvent<'_>),
    ) {
        match &result {
            Ok(config) => {
                if let Ok(mut previous) = self.last_config.lock() {
                    if previous.as_ref() != Some(config) {
                        *previous = Some(config.clone());
                        publish(ServiceEvent::Changed(config));
                    }
                }
                if let Ok(mut error) = self.service_error.lock() {
                    *error = None;
                }
            }
            Err(message) => {
                if let Ok(mut previous) = self.last_config.lock() {
                    *previous = None;
                }
                if let Ok(mut error) = self.service_error.lock() {
                    if error.as_ref() != Some(message) {
                        eprintln!(
                            "Не удалось запустить или восстановить локальные службы: {message}"
                        );
                        *error = Some(message.clone());
                        publish(ServiceEvent::Error(message));
                    }
                }
            }
        }
    }

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
        let python = self.python_executable();

        let log_path = self.state_dir.join("desktop-worker.log");
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
                .env("DISPLAY", display);
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

            let _log = match process_log::LogDrain::attach(&mut command, &log_path) {
                Ok(log) => log,
                Err(error) => {
                    let _ = startup_tx.send(Err(error));
                    return;
                }
            };
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
                    stop_child_gracefully(
                        &mut child,
                        Duration::from_secs(12),
                        Duration::from_secs(3),
                    );
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
            "https://market.yandex.ru/",
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
            *self
                .manual_browser_log
                .lock()
                .map_err(|_| "Ошибка журнала Chrome")? = None;
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
        let mut command = Command::new(executable);
        command
            .arg("--remote-debugging-port=0")
            .arg("--remote-debugging-address=127.0.0.1")
            .arg(format!("--user-data-dir={}", profile.display()))
            .args([
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                "--ozone-platform=x11",
            ])
            .args(store_urls);
        // A second Chrome launcher only sends URLs to the existing owned
        // process; it must not reset or become another writer of that log.
        let log = if existing_port.is_none() {
            Some(process_log::LogDrain::attach(&mut command, &log_path)?)
        } else {
            command.stdout(Stdio::null()).stderr(Stdio::null());
            None
        };
        let mut child = command
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
            *self
                .manual_browser_log
                .lock()
                .map_err(|_| "Ошибка журнала Chrome")? = log;
        } else {
            thread::spawn(move || {
                let _ = child.wait();
            });
        }
        Ok(())
    }

    fn request_profile_browser_close(&self) -> Result<(), String> {
        let mut closer = Command::new(self.python_executable())
            .args([
                "-c",
                "from marketplace_connector.browser.profile_lifecycle import main; raise SystemExit(main())",
            ])
            .arg(&self.profile_dir)
            .current_dir(&self.project_root)
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("Не удалось запустить закрытие Chrome: {error}"))?;
        if !wait_for_worker_exit(&mut closer, Duration::from_secs(12)) {
            let _ = closer.kill();
            let _ = closer.wait();
            return Err("Ожидание штатного закрытия Chrome превысило 12 секунд".to_string());
        }
        let output = closer
            .wait_with_output()
            .map_err(|error| format!("Не удалось проверить закрытие Chrome: {error}"))?;
        if output.status.success() {
            Ok(())
        } else {
            Err(format!(
                "Не удалось штатно закрыть Chrome: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ))
        }
    }

    fn stop_manual_browser(&self) -> Result<(), String> {
        let _log = self
            .manual_browser_log
            .lock()
            .map_err(|_| "Ошибка журнала Chrome")?
            .take();
        let mut browser = self
            .manual_browser
            .lock()
            .map_err(|_| "Ошибка состояния Chrome")?;
        let Some(mut child) = browser.take() else {
            return Ok(());
        };
        if child
            .try_wait()
            .map_err(|error| format!("Не удалось проверить Chrome: {error}"))?
            .is_some()
        {
            return Ok(());
        }

        let close_result = self.request_profile_browser_close();
        if !wait_for_worker_exit(&mut child, Duration::from_secs(5)) {
            eprintln!("Chrome не завершился штатно; посылаю SIGTERM");
            #[cfg(target_os = "linux")]
            unsafe {
                libc::kill(child.id() as i32, libc::SIGTERM);
            }
            if !wait_for_worker_exit(&mut child, Duration::from_secs(3)) {
                eprintln!("Chrome завис; посылаю SIGKILL");
                let _ = child.kill();
            }
        }
        let _ = child.wait();
        if active_debug_port(&self.profile_dir).is_some() {
            return Err("Chrome не освободил профиль после закрытия".to_string());
        }
        close_result
    }

    fn prepare_collection(&self) -> Result<(), String> {
        self.prepare_user_paths()?;
        self.stop_manual_browser()?;
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
    use super::{
        active_debug_port, is_background_launch, migrate_profile, stop_child_gracefully, ApiConfig,
        RuntimeState, ServiceEvent,
    };
    use std::{
        fs,
        io::{BufRead, BufReader},
        path::PathBuf,
        process::{Command, Stdio},
        sync::{Arc, Mutex},
        thread,
        time::{Duration, Instant, SystemTime, UNIX_EPOCH},
    };

    fn signal_test_child(script: &str, marker: &std::path::Path) -> std::process::Child {
        let mut child = Command::new("python3")
            .args(["-u", "-c", script])
            .arg(marker)
            .stdout(Stdio::piped())
            .spawn()
            .expect("test Python process should start");
        let mut ready = String::new();
        BufReader::new(child.stdout.take().unwrap())
            .read_line(&mut ready)
            .unwrap();
        assert_eq!(ready, "ready\n");
        child
    }

    #[test]
    fn graceful_worker_stop_sends_sigint_before_fallback() {
        let marker =
            std::env::temp_dir().join(format!("price-watch-sigint-{}", std::process::id()));
        let mut child = signal_test_child(
            "import signal,sys,time\ndef stop(sig, frame):\n open(sys.argv[1], 'w').write('sigint')\n sys.exit(0)\nsignal.signal(signal.SIGINT, stop)\nprint('ready')\nwhile True: time.sleep(.1)",
            &marker,
        );
        stop_child_gracefully(
            &mut child,
            Duration::from_secs(2),
            Duration::from_millis(100),
        );
        assert_eq!(fs::read_to_string(&marker).unwrap(), "sigint");
        assert!(child.try_wait().unwrap().is_some());
        fs::remove_file(marker).unwrap();
    }

    #[test]
    fn unresponsive_worker_is_killed_after_bounded_wait() {
        let marker =
            std::env::temp_dir().join(format!("price-watch-fallback-{}", std::process::id()));
        let mut child = signal_test_child(
            "import signal,time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint('ready')\nwhile True: time.sleep(.1)",
            &marker,
        );
        stop_child_gracefully(
            &mut child,
            Duration::from_millis(150),
            Duration::from_millis(150),
        );
        assert!(child.try_wait().unwrap().is_some());
        assert!(!marker.exists());
    }

    #[test]
    fn recognizes_only_explicit_background_flag() {
        assert!(is_background_launch([
            "price-watch".into(),
            "--background".into()
        ]));
        assert!(!is_background_launch(["price-watch".into()]));
        assert!(!is_background_launch([
            "price-watch".into(),
            "--background=false".into()
        ]));
    }

    #[test]
    fn service_events_replace_failed_or_stale_api_connections() {
        let runtime = RuntimeState {
            project_root: PathBuf::new(),
            profile_dir: PathBuf::new(),
            data_dir: PathBuf::new(),
            state_dir: PathBuf::new(),
            config_dir: PathBuf::new(),
            native: Mutex::new(None),
            worker: Mutex::new(None),
            manual_browser: Mutex::new(None),
            manual_browser_log: Mutex::new(None),
            startup: Mutex::new(()),
            last_config: Mutex::new(None),
            service_error: Mutex::new(None),
        };
        let first = ApiConfig {
            base_url: "http://127.0.0.1:49123".into(),
            token: Some("first".into()),
        };
        let second = ApiConfig {
            base_url: "http://127.0.0.1:49124".into(),
            token: Some("second".into()),
        };
        let mut events = Vec::new();
        let mut record = |event: ServiceEvent<'_>| match event {
            ServiceEvent::Changed(config) => events.push(format!(
                "changed:{}:{}",
                config.base_url,
                config.token.as_deref().unwrap()
            )),
            ServiceEvent::Error(message) => events.push(format!("error:{message}")),
        };

        runtime.record_service_result(&Ok(first.clone()), &mut record);
        runtime.record_service_result(&Ok(first), &mut record);
        runtime.record_service_result(&Err("API недоступен".into()), &mut record);
        runtime.record_service_result(&Err("API недоступен".into()), &mut record);
        assert!(runtime.last_config.lock().unwrap().is_none());
        assert_eq!(
            runtime.service_error.lock().unwrap().as_deref(),
            Some("API недоступен")
        );
        runtime.record_service_result(&Ok(second.clone()), &mut record);
        drop(record);

        assert_eq!(
            events,
            [
                "changed:http://127.0.0.1:49123:first",
                "error:API недоступен",
                "changed:http://127.0.0.1:49124:second",
            ]
        );
        assert!(runtime.last_config.lock().unwrap().as_ref() == Some(&second));
        assert!(runtime.service_error.lock().unwrap().is_none());
    }

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
    #[ignore = "requires system Google Chrome and the project Python dependencies"]
    fn closes_manual_chrome_cleanly_in_a_temporary_profile() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let profile = std::env::temp_dir().join(format!(
            "price-watch-chrome-test-{}-{unique}",
            std::process::id()
        ));
        fs::create_dir_all(&profile).unwrap();
        let child = Command::new("google-chrome-stable")
            .args([
                "--headless=new",
                "--remote-debugging-port=0",
                "--no-first-run",
            ])
            .arg(format!("--user-data-dir={}", profile.display()))
            .arg("about:blank")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(10);
        while active_debug_port(&profile).is_none() {
            assert!(Instant::now() < deadline, "Chrome did not open CDP");
            thread::sleep(Duration::from_millis(100));
        }
        let runtime = RuntimeState {
            project_root: std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."),
            profile_dir: profile.clone(),
            data_dir: PathBuf::new(),
            state_dir: PathBuf::new(),
            config_dir: PathBuf::new(),
            native: Mutex::new(None),
            worker: Mutex::new(None),
            manual_browser: Mutex::new(Some(child)),
            manual_browser_log: Mutex::new(None),
            startup: Mutex::new(()),
            last_config: Mutex::new(None),
            service_error: Mutex::new(None),
        };
        runtime.stop_manual_browser().unwrap();
        assert!(runtime.manual_browser.lock().unwrap().is_none());
        assert!(active_debug_port(&profile).is_none());
        let preferences = fs::read_to_string(profile.join("Default/Preferences")).unwrap();
        assert!(preferences.contains("\"exit_type\":\"Normal\""));
        fs::remove_dir_all(profile).unwrap();
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
            manual_browser_log: Mutex::new(None),
            startup: Mutex::new(()),
            last_config: Mutex::new(None),
            service_error: Mutex::new(None),
        };
        let config = runtime
            .ensure_services()
            .expect("native runtime should start");
        assert!(config.token.is_some());
        let initial_worker = Arc::clone(&runtime.worker.lock().unwrap().as_ref().unwrap().running);
        let repeat = runtime
            .ensure_services()
            .expect("native runtime should be reusable");
        assert!(
            config == repeat,
            "repeated ensure must retain the API connection"
        );
        assert!(Arc::ptr_eq(
            &initial_worker,
            &runtime.worker.lock().unwrap().as_ref().unwrap().running,
        ));
        std::thread::sleep(std::time::Duration::from_millis(750));
        assert!(runtime.worker_is_running().unwrap());
        assert!(runtime.native.lock().unwrap().as_mut().unwrap().is_ready());
        assert!(!runtime.profile_dir.join("DevToolsActivePort").exists());
        runtime.stop_worker();
        assert!(!runtime.worker_is_running().unwrap());
        runtime
            .ensure_services()
            .expect("stopped worker should restart");
        assert!(runtime.worker_is_running().unwrap());
        assert!(!Arc::ptr_eq(
            &initial_worker,
            &runtime.worker.lock().unwrap().as_ref().unwrap().running,
        ));

        let mut previous = repeat;
        for service in ["api", "display", "postgres"] {
            runtime
                .native
                .lock()
                .unwrap()
                .as_mut()
                .unwrap()
                .stop_service_for_test(service);
            let recovered = runtime
                .ensure_services()
                .unwrap_or_else(|error| panic!("{service} should recover: {error}"));
            assert_ne!(
                recovered.token, previous.token,
                "{service} must replace the API token"
            );
            assert!(
                runtime.worker_is_running().unwrap(),
                "{service} must restart the worker"
            );
            previous = recovered;
        }
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
    env::var_os("PRICE_WATCH_PROJECT_DIR")
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

fn is_background_launch(args: impl IntoIterator<Item = String>) -> bool {
    args.into_iter()
        .skip(1)
        .any(|argument| argument == "--background")
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn install_tray(app: &mut tauri::App) -> tauri::Result<()> {
    use tauri::{
        menu::{MenuBuilder, MenuItemBuilder},
        tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    };

    let open = MenuItemBuilder::with_id("open", "Открыть price-watch").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Выход").build(app)?;
    let menu = MenuBuilder::new(app).items(&[&open, &quit]).build()?;
    let mut tray = TrayIconBuilder::new()
        .menu(&menu)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "open" => show_main_window(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    tray.build(app)?;
    Ok(())
}

#[tauri::command]
async fn ensure_services(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<RuntimeState>>,
) -> Result<ApiConfig, String> {
    let state = Arc::clone(state.inner());
    tauri::async_runtime::spawn_blocking(move || state.ensure_and_publish(&app))
        .await
        .map_err(|error| format!("Ошибка задачи запуска: {error}"))?
}

#[tauri::command]
fn get_background_state(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<RuntimeState>>,
) -> Result<BackgroundState, String> {
    let enabled = app
        .autolaunch()
        .is_enabled()
        .map_err(|error| error.to_string())?;
    let service_error = state
        .service_error
        .lock()
        .map_err(|_| "Ошибка состояния служб")?
        .clone();
    Ok(BackgroundState {
        enabled,
        service_error,
    })
}

#[tauri::command]
fn set_background_enabled(
    app: tauri::AppHandle,
    state: tauri::State<'_, Arc<RuntimeState>>,
    enabled: bool,
) -> Result<BackgroundState, String> {
    if enabled {
        app.autolaunch()
            .enable()
            .map_err(|error| format!("Не удалось включить фоновый режим: {error}"))?;
    } else {
        app.autolaunch()
            .disable()
            .map_err(|error| format!("Не удалось отключить фоновый режим: {error}"))?;
    }
    get_background_state(app, state)
}

#[tauri::command]
fn quit_app(app: tauri::AppHandle) {
    app.exit(0);
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
    let background_launch = is_background_launch(env::args());
    let mut context = tauri::generate_context!();
    if background_launch {
        if let Some(main) = context
            .config_mut()
            .app
            .windows
            .iter_mut()
            .find(|window| window.label == "main")
        {
            main.visible = false;
        }
    }
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
        manual_browser_log: Mutex::new(None),
        startup: Mutex::new(()),
        last_config: Mutex::new(None),
        service_error: Mutex::new(None),
    });
    let cleanup = Arc::clone(&runtime);
    let setup_runtime = Arc::clone(&runtime);
    let monitor_shutdown = Arc::new(AtomicBool::new(false));
    let setup_shutdown = Arc::clone(&monitor_shutdown);
    let monitor_join = Arc::new(Mutex::new(None::<JoinHandle<()>>));
    let setup_join = Arc::clone(&monitor_join);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            show_main_window(app)
        }))
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--background"]),
        ))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .manage(runtime)
        .invoke_handler(tauri::generate_handler![
            ensure_services,
            get_background_state,
            set_background_enabled,
            quit_app,
            open_store_browser,
            prepare_collection,
            save_export_file
        ])
        .setup(move |app| {
            if let Err(error) = install_tray(app) {
                eprintln!("Не удалось создать значок в системном tray: {error}");
            }
            if background_launch {
                if let Some(window) = app.get_webview_window("main") {
                    window.hide()?;
                }
            }
            let handle = app.handle().clone();
            let runtime = Arc::clone(&setup_runtime);
            let shutdown = Arc::clone(&setup_shutdown);
            let monitor = thread::spawn(move || {
                // Own the services independently of the webview. Failed starts are
                // retried at most once every five seconds while the app is alive.
                while !shutdown.load(Ordering::Acquire) {
                    let _ = runtime.ensure_and_publish(&handle);
                    for _ in 0..50 {
                        if shutdown.load(Ordering::Acquire) {
                            return;
                        }
                        thread::sleep(Duration::from_millis(100));
                    }
                }
            });
            *setup_join
                .lock()
                .map_err(|_| "Ошибка запуска монитора служб")? = Some(monitor);
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window
                    .app_handle()
                    .autolaunch()
                    .is_enabled()
                    .unwrap_or(false)
                {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .build(context)
        .expect("Не удалось собрать Tauri-приложение");

    app.run(move |_app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            monitor_shutdown.store(true, Ordering::Release);
            if let Ok(mut monitor) = monitor_join.lock() {
                if let Some(monitor) = monitor.take() {
                    let _ = monitor.join();
                }
            }
            cleanup.stop_worker();
            if let Err(error) = cleanup.stop_manual_browser() {
                eprintln!("{error}");
            }
            if let Ok(mut native) = cleanup.native.lock() {
                *native = None;
            }
        }
    });
}
