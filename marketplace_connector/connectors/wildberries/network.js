({maxInFlight, timeoutMs, maxRetryWaitMs}) => {
    // Installed before the storefront scripts capture fetch. Only SDK detail,
    // wallet and article metadata requests belong to the collection budget.
    const nativeFetch = globalThis.fetch.bind(globalThis);
    const owners = new Map();
    const retired = new Set();
    const pending = new Set();
    const active = new Set();
    const state = globalThis.__priceWatchWbNetwork = {owners, retired, active, pending, peak: 0, requests: 0, queueMs: 0, httpMs: 0};
    let cooldown = 0;
    let wakeTimer;
    const identify = input => {
        const u = new URL(input instanceof Request ? input.url : String(input), location.href);
        if (u.hostname === 'wildberries.ru' || u.hostname.endsWith('.wildberries.ru') || u.hostname === 'wb.ru' || u.hostname.endsWith('.wb.ru')) {
            if (u.pathname.endsWith('/v6/grade')) return 'profile';
            if (u.pathname.includes('/cards/v4/detail')) {
                const ids = (u.searchParams.get('nm') ?? '').split(',');
                const owned = ids.filter(id => owners.has(id) || retired.has(id));
                if (owned.length > 1) throw Error('WB: unexpected native request batching');
                return owned[0] ?? null;
            }
        }
        if (u.hostname.endsWith('.wbbasket.ru') || u.hostname.endsWith('.wildberries.ru')) {
            const match = u.pathname.match(/\/(\d+)\/info\/[^/]+\/card\.json$/);
            if (match && (owners.has(match[1]) || retired.has(match[1]))) return match[1];
        }
        return null;
    };
    const pump = () => {
        clearTimeout(wakeTimer);
        for (const waiter of pending) {
            if (waiter.signal.aborted) { pending.delete(waiter); waiter.reject(waiter.signal.reason); }
        }
        if (state.paused) return;
        const delay = cooldown - performance.now();
        if (delay > maxRetryWaitMs) {
            for (const w of pending) w.reject(Error('WB: Retry-After exceeds retry budget'));
            pending.clear();
            return;
        }
        if (delay > 0) { wakeTimer = setTimeout(pump, delay); return; }
        for (const w of pending) {
            if (active.size >= maxInFlight) break;
            pending.delete(w);
            active.add(w);
            state.peak = Math.max(state.peak, active.size);
            w.resolve(w);
        }
    };
    const acquire = (article, signal) => new Promise((resolve, reject) => {
        const w = {article, signal, resolve, reject};
        pending.add(w);
        signal.addEventListener('abort', pump, {once: true});
        pump();
    });
    const retryAfter = response => {
        if (response.status !== 429) return;
        const raw = response.headers.get('retry-after');
        let ms = /^\d+$/.test(raw ?? '') ? Number(raw) * 1000 : Date.parse(raw) - Date.now();
        if (Number.isNaN(ms)) ms = 1000;
        cooldown = Math.max(cooldown, performance.now() + Math.max(0, ms));
    };
    globalThis.fetch = async (input, options = {}) => {
        const article = identify(input);
        if (article === null) return nativeFetch(input, options);
        if (retired.has(article)) throw new DOMException('WB owner stopped', 'AbortError');
        const parent = article === 'profile' ? null : owners.get(article);
        const controller = new AbortController();
        // WB fetchStatic arms its own 30s AbortSignal before fetch. That
        // deadline includes our pending queue, so replace it for owned HTTP.
        // Target cancellation comes from the owner, profile initialization is
        // shared, and the sole HTTP timer starts after acquire below.
        const signals = [controller.signal, parent?.signal].filter(Boolean);
        const signal = AbortSignal.any(signals);
        const queued = performance.now();
        const slot = await acquire(article, signal);
        const started = performance.now();
        state.requests++;
        state.queueMs += started - queued;
        // Both timeout and network I/O start only after admission.
        const timer = setTimeout(() => controller.abort(new DOMException('WB HTTP timeout', 'TimeoutError')), timeoutMs);
        try {
            const response = await nativeFetch(input, {...options, signal});
            retryAfter(response);
            if ([401, 403, 498].includes(response.status)) state.paused = true;
            // The native runtime still receives its original Response. Reading
            // the clone keeps the permit until the complete body or abort.
            await response.clone().arrayBuffer();
            return response;
        } finally {
            state.httpMs += performance.now() - started;
            clearTimeout(timer);
            active.delete(slot);
            pump();
        }
    };
    // A newly introduced XHR SDK path must fail explicitly rather than bypass
    // the budget. Fetch is the supported native bridge; Python observes this.
    const nativeOpen = XMLHttpRequest.prototype.open;
    const nativeSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url, ...args) {
        this.__priceWatchUrl = url;
        return nativeOpen.call(this, method, url, ...args);
    };
    XMLHttpRequest.prototype.send = function(...args) {
        if (identify(String(this.__priceWatchUrl)) !== null) {
            state.unsupportedXHR = true;
            throw Error('WB: native XHR collection path is unsupported');
        }
        return nativeSend.apply(this, args);
    };
}
