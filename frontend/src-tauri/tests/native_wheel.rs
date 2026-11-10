//! Isolated GTK/WebKit regression test; requires a display (e.g. xvfb-run).
#![cfg(target_os = "linux")]
#![allow(deprecated)]

#[path = "../src/webview_settings.rs"]
#[allow(dead_code)]
mod webview_settings;

use gtk::{gdk, glib, prelude::*};
use std::{
    cell::Cell,
    ffi::CStr,
    rc::Rc,
    time::{Duration, Instant},
};
use webkit2gtk::{WebContext, WebView, WebViewExt};

#[link(name = "javascriptcoregtk-4.1")]
extern "C" {
    fn jsc_value_to_json(value: *mut std::ffi::c_void, indent: u32) -> *mut std::ffi::c_char;
}

fn spin(milliseconds: u64) {
    let until = Instant::now() + Duration::from_millis(milliseconds);
    while Instant::now() < until {
        glib::MainContext::default().iteration(false);
        std::thread::sleep(Duration::from_millis(1));
    }
}

fn js(view: &WebView, script: &str) -> String {
    let result = glib::MainContext::default()
        .block_on(view.run_javascript_future(script))
        .expect("JavaScript evaluation");
    let value = result.js_value().unwrap();
    // SAFETY: JSC owns the live value. to_json returns an allocated UTF-8 string.
    unsafe {
        let text = jsc_value_to_json(value.as_ptr().cast(), 0);
        assert!(!text.is_null());
        let json = CStr::from_ptr(text).to_string_lossy().into_owned();
        glib::ffi::g_free(text.cast());
        json
    }
}

fn number(view: &WebView, script: &str) -> f64 {
    js(view, script).parse().unwrap()
}

fn wheel(view: &WebView, direction: gdk::ScrollDirection, state: gdk::ModifierType, nested: bool) {
    let mut event = gdk::Event::new(gdk::EventType::Scroll);
    let window = gtk::prelude::WidgetExt::window(view).unwrap();
    let pointer = gdk::Display::default()
        .unwrap()
        .default_seat()
        .unwrap()
        .pointer()
        .unwrap();
    event.set_device(Some(&pointer));
    event.set_source_device(Some(&pointer));
    let data = event.downcast_mut::<gdk::EventScroll>().unwrap().as_mut();
    data.window = window.to_glib_full();
    data.direction = direction.into_glib();
    data.time = (glib::monotonic_time() / 1000) as u32;
    data.x = if nested { 450.0 } else { 100.0 };
    data.y = 150.0;
    data.x_root = data.x;
    data.y_root = data.y;
    data.delta_x = 0.0;
    data.delta_y = 1.0;
    data.state = state.bits();
    gtk::main_do_event(&mut event);
}

use glib::translate::{IntoGlib, ToGlibPtr};

fn distance(accelerated: bool) -> (f64, Vec<f64>, f64) {
    let view = WebView::with_context(&WebContext::new_ephemeral());
    if accelerated {
        webview_settings::accelerate_mouse_wheel(&view);
    }
    let deliveries = Rc::new(Cell::new(0));
    let observed = deliveries.clone();
    view.connect_scroll_event(move |_, _| {
        observed.set(observed.get() + 1);
        // Fail safely rather than let a regressed handler flood the test process.
        if observed.get() >= 500 {
            return glib::Propagation::Stop;
        }
        glib::Propagation::Proceed
    });
    let window = gtk::Window::new(gtk::WindowType::Toplevel);
    window.set_default_size(800, 600);
    window.add(&view);
    window.show_all();
    let loaded = Rc::new(Cell::new(false));
    let ready = loaded.clone();
    view.connect_load_changed(move |_, event| {
        if event == webkit2gtk::LoadEvent::Finished {
            ready.set(true);
        }
    });
    view.load_html("<style>body{margin:0;height:12000px}#inner{position:fixed;left:400px;top:100px;width:200px;height:200px;overflow:auto}#content{height:2000px}</style><div id=inner><div id=content></div></div><script>var wheels=0,lastX=0,lastY=0;addEventListener('wheel',e=>{wheels++;lastX=e.deltaX;lastY=e.deltaY},{passive:true})</script>", None);
    let deadline = Instant::now() + Duration::from_secs(10);
    while !loaded.get() {
        assert!(Instant::now() < deadline, "page load timeout");
        spin(10);
    }
    js(&view, "scrollTo(0,1000);wheels=0");
    spin(100);
    wheel(
        &view,
        gdk::ScrollDirection::Down,
        gdk::ModifierType::empty(),
        false,
    );
    spin(350);
    let delta = number(&view, "scrollY") - 1000.0;
    assert_eq!(number(&view, "wheels"), 1.0, "one DOM event per input");
    assert!(delta > 0.0);

    // Smooth mouse input and modified/horizontal wheel keep one DOM delivery.
    let mut deltas = Vec::new();
    for (direction, modifiers) in [
        (gdk::ScrollDirection::Smooth, gdk::ModifierType::empty()),
        (gdk::ScrollDirection::Down, gdk::ModifierType::SHIFT_MASK),
        (gdk::ScrollDirection::Down, gdk::ModifierType::CONTROL_MASK),
        (gdk::ScrollDirection::Down, gdk::ModifierType::MOD1_MASK),
        (gdk::ScrollDirection::Down, gdk::ModifierType::SUPER_MASK),
        (gdk::ScrollDirection::Down, gdk::ModifierType::META_MASK),
        (gdk::ScrollDirection::Right, gdk::ModifierType::empty()),
    ] {
        js(&view, "wheels=0");
        wheel(&view, direction, modifiers, false);
        spin(150);
        assert_eq!(number(&view, "wheels"), 1.0);
        deltas.push(number(&view, "Math.abs(lastX)+Math.abs(lastY)"));
    }

    js(&view, "scrollTo(0,1000);inner.scrollTop=0;wheels=0");
    spin(100);
    wheel(
        &view,
        gdk::ScrollDirection::Down,
        gdk::ModifierType::empty(),
        true,
    );
    spin(350);
    let nested_delta = number(&view, "inner.scrollTop");
    assert!(nested_delta > 0.0);
    assert_eq!(
        number(&view, "scrollY"),
        1000.0,
        "native nested scroll routing"
    );

    // At both boundaries WebKit asynchronously returns unhandled events to GTK.
    // The former two-copy redispatch handler multiplied those returned events.
    for (position, direction, nested) in [
        ("12000", gdk::ScrollDirection::Down, false),
        ("0", gdk::ScrollDirection::Up, false),
        ("12000", gdk::ScrollDirection::Down, true),
    ] {
        js(
            &view,
            &format!("scrollTo(0,{position});inner.scrollTop=2000;wheels=0"),
        );
        spin(100);
        deliveries.set(0);
        for _ in 0..20 {
            wheel(&view, direction, gdk::ModifierType::empty(), nested);
            spin(5);
        }
        spin(350);
        println!(
            "boundary {position}, nested={nested}: DOM={}, GTK={}",
            number(&view, "wheels"),
            deliveries.get()
        );
        assert!(
            number(&view, "wheels") <= 20.0,
            "no DOM event multiplication at boundary"
        );
        assert!(
            deliveries.get() <= 40,
            "at most input plus native return per wheel"
        );
        let count = deliveries.get();
        spin(200);
        assert_eq!(deliveries.get(), count, "native queue settles");
    }
    window.close();
    spin(50);
    (delta, deltas, nested_delta)
}

#[test]
#[ignore = "requires GTK/WebKit display; run under xvfb-run with --ignored --test-threads=1"]
fn mouse_wheel_keeps_native_delivery_and_doubles_distance() {
    gtk::init().unwrap();
    let (original, original_deltas, original_nested) = distance(false);
    let (accelerated, accelerated_deltas, accelerated_nested) = distance(true);
    println!("native distance {original}, accelerated {accelerated}");
    assert!((accelerated / original - 2.0).abs() < 0.05);
    assert!((accelerated_nested / original_nested - 2.0).abs() < 0.05);
    assert_eq!(
        accelerated_deltas[0],
        original_deltas[0] * 2.0,
        "smooth mouse distance"
    );
    assert_eq!(
        &accelerated_deltas[1..],
        &original_deltas[1..],
        "modified and horizontal input unchanged"
    );
}
