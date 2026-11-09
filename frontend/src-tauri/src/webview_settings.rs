use gtk::{gdk, glib::Propagation, prelude::*};
use std::cell::Cell;
use std::ffi::{c_char, c_int, c_void, CStr};
use webkit2gtk::{glib::object::ObjectType, WebViewExt};

// webkit2gtk 2.0.2 does not bind the feature API (WebKitGTK 2.42+).
// Keep this small bridge on the public C API until the Rust bindings expose it.
#[link(name = "webkit2gtk-4.1")]
extern "C" {
    fn webkit_settings_get_all_features() -> *mut c_void;
    fn webkit_feature_list_get_length(list: *mut c_void) -> usize;
    fn webkit_feature_list_get(list: *mut c_void, index: usize) -> *mut c_void;
    fn webkit_feature_get_identifier(feature: *mut c_void) -> *const c_char;
    fn webkit_feature_list_unref(list: *mut c_void);
    fn webkit_settings_set_feature_enabled(
        settings: *mut c_void,
        feature: *mut c_void,
        enabled: c_int,
    );
    fn webkit_settings_get_feature_enabled(settings: *mut c_void, feature: *mut c_void) -> c_int;
}

pub fn allow_display_refresh_rate(view: &webkit2gtk::WebView) -> Result<(), &'static str> {
    let settings = WebViewExt::settings(view).ok_or("WebKit settings unavailable")?;
    // SAFETY: Called on the GTK UI thread by Tauri. Settings remain alive;
    // feature pointers and identifiers are borrowed only while the owned list
    // is alive. Every path after allocation releases that list exactly once.
    unsafe {
        let list = webkit_settings_get_all_features();
        if list.is_null() {
            return Err("WebKit feature list unavailable");
        }
        let mut result = Err("PreferPageRenderingUpdatesNear60FPS feature unavailable");
        for index in 0..webkit_feature_list_get_length(list) {
            let feature = webkit_feature_list_get(list, index);
            let identifier = webkit_feature_get_identifier(feature);
            if CStr::from_ptr(identifier).to_bytes() == b"PreferPageRenderingUpdatesNear60FPS" {
                let pointer = settings.as_ptr().cast();
                webkit_settings_set_feature_enabled(pointer, feature, 0);
                result = if webkit_settings_get_feature_enabled(pointer, feature) == 0 {
                    Ok(())
                } else {
                    Err("WebKit did not disable the 60 FPS preference")
                };
                break;
            }
        }
        webkit_feature_list_unref(list);
        result
    }
}

/// Double physical mouse wheel steps without taking scrolling away from WebKit.
pub fn accelerate_mouse_wheel(view: &webkit2gtk::WebView) {
    let redispatching = Cell::new(false);
    view.connect_scroll_event(move |_, event| {
        if redispatching.get() {
            return Propagation::Proceed;
        }
        let modifiers = gdk::ModifierType::CONTROL_MASK
            | gdk::ModifierType::SHIFT_MASK
            | gdk::ModifierType::MOD1_MASK
            | gdk::ModifierType::SUPER_MASK
            | gdk::ModifierType::META_MASK;
        if event.state().intersects(modifiers) {
            return Propagation::Proceed;
        }
        let vertical = match event.direction() {
            gdk::ScrollDirection::Up | gdk::ScrollDirection::Down => true,
            gdk::ScrollDirection::Smooth => {
                let (x, y) = event.delta();
                x == 0.0 && y != 0.0 && !event.is_stop()
            }
            _ => false,
        };
        let mouse = match event.source_device().map(|device| device.source()) {
            Some(gdk::InputSource::Mouse) => true,
            None => matches!(
                event.direction(),
                gdk::ScrollDirection::Up | gdk::ScrollDirection::Down
            ),
            _ => false,
        };
        if !vertical || !mouse {
            return Propagation::Proceed;
        }
        // Route owned copies through GTK so WebKit retains hit-testing,
        // nested scrolling and native animation. Re-entry must not multiply again.
        redispatching.set(true);
        for _ in 0..2 {
            let mut copy = event.clone();
            gtk::main_do_event(&mut copy);
        }
        redispatching.set(false);
        Propagation::Stop
    });
}
