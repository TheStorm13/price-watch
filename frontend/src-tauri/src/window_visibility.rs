/// One opening policy for startup, tray and second-instance requests.
/// Readiness is reported after the frontend renders either the app or a startup error.
pub struct WindowVisibility {
    pub ready: bool,
    pub requested: bool,
    pub timed_out: bool,
}

impl WindowVisibility {
    pub fn new(background: bool) -> Self {
        Self {
            ready: false,
            requested: !background,
            timed_out: false,
        }
    }

    pub fn request_open(&mut self) -> bool {
        self.requested = true;
        self.take_open()
    }

    pub fn rendered(&mut self) -> bool {
        self.ready = true;
        self.timed_out = false;
        self.take_open()
    }

    fn take_open(&mut self) -> bool {
        if self.ready && self.requested {
            self.requested = false;
            true
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordinary_launch_waits_for_render_and_opens_only_once() {
        let mut state = WindowVisibility::new(false);
        assert!(state.rendered());
        assert!(!state.rendered()); // recovery must not reveal a hidden window
        assert!(state.request_open());
    }

    #[test]
    fn background_launch_remains_hidden_until_requested() {
        let mut state = WindowVisibility::new(true);
        assert!(!state.rendered());
        assert!(state.request_open());
        assert!(!state.rendered());
    }

    #[test]
    fn requests_during_startup_are_queued() {
        let mut state = WindowVisibility::new(true);
        assert!(!state.request_open());
        assert!(!state.request_open());
        assert!(state.rendered());
        assert!(!state.rendered());
    }
}
