fn main() {
    println!("cargo:rerun-if-env-changed=STATIC_VCRUNTIME");
    // Preserve the legacy override without letting tauri-build emit its deprecation warning.
    let legacy_override = std::env::var_os("STATIC_VCRUNTIME").map(|value| value != "false");
    std::env::remove_var("STATIC_VCRUNTIME");
    let mut windows = tauri_build::WindowsAttributes::new();
    if let Some(value) = legacy_override {
        windows = windows.static_vc_runtime(value);
    }
    tauri_build::try_build(tauri_build::Attributes::new().windows_attributes(windows))
        .expect("failed to run tauri-build");
}
