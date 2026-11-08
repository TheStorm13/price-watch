async ({id, nmId, timeoutMs}) => {
    const registry = globalThis.__priceWatchWbRequests ??= new Map();
    const controller = new AbortController();
    const network = globalThis.__priceWatchWbNetwork;
    network.owners.set(nmId, controller);
    let finished;
    const done = new Promise(resolve => { finished = resolve; });
    registry.set(id, {controller, done});
    const waitNative = (promise, article = nmId) => {
        // A native Promise can remain unresolved even after its HTTP finished.
        // This watchdog measures only time with no owned queued/active HTTP;
        // it is not an HTTP or queue deadline. Unknown native work is fatal.
        let idleSince = performance.now();
        let timer;
        const guard = new Promise((_, reject) => {
            timer = setInterval(() => {
                const busy = [...network.pending, ...network.active].some(r => r.article === article);
                const now = performance.now();
                if (busy) idleSince = now;
                else if (now - idleSince >= timeoutMs) {
                    network.retired.add(nmId);
                    reject(Object.assign(new Error('WB native runtime did not settle'), {unsafe: true}));
                }
            }, Math.max(10, Math.min(100, timeoutMs / 4)));
        });
        return Promise.race([promise, guard]).finally(() => clearInterval(timer));
    };
    const fail = message => { throw new Error(message); };
    const money = (value, integer = false) => {
        if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 ||
            (integer && !Number.isSafeInteger(value))) fail('Некорректная сумма WB');
        return String(value);
    };
    const safeId = value => {
        if (!Number.isSafeInteger(value) || value <= 0) fail('Некорректный ID ответа WB');
        return String(value);
    };
    const prepareProfile = async w => {
        // Globals appear before the host instance is initialized. Calling Xnm
        // in that interval can leave its Promise pending forever (its prerequisite
        // Promise.all has no rejection handler). Wait for the native profile
        // context first; never supply a probe/default region in its place.
        let profileReady = false;
        const deadline = performance.now() + timeoutMs;
        while (performance.now() < deadline) {
            try {
                const xinfo = await waitNative(w.user.getXinfo(), 'profile');
                if (typeof xinfo === 'string' && xinfo.length > 0) {
                    profileReady = true;
                    break;
                }
            } catch (error) {
                if (error?.unsafe) throw error;
                /* The host may still be initializing. */
            }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        if (!profileReady) fail('WB: контекст профиля не готов');
        if (w.user.getCurrency() !== 'RUB') fail('WB: требуется валюта RUB');
    };
    const fresh = value => Number.isFinite(value) && value > Date.now();
    const validPercent = value => Number.isFinite(value) && value >= 0 && value <= 100;
    const prepareWallet = async w => {
        // getUserGrade is auth-aware and returns null for an anonymous profile.
        const grade = await waitNative(w.user.getUserGrade('RUB'), 'profile');
        if (grade === null) {
            await waitNative(w.user.setDiscountForUnAuth(), 'profile');
            let cache;
            try { cache = JSON.parse(localStorage.getItem('wbx_default_discounts')); } catch {}
            if (!cache || !fresh(cache.expire) || cache.wctype_id !== 1 || !validPercent(cache.discount_value))
                fail('WB: условия кошелька не готовы');
        } else {
            if (!grade || !fresh(grade.expire) || grade.currency !== 'RUB' || !Array.isArray(grade.payments))
                fail('WB: условия профиля не готовы');
            for (const p of grade.payments.filter(p => p.wctype_id === 1)) {
                if (!validPercent(p.discount_value))
                    fail('WB: повреждены условия кошелька');
            }
        }
    };
    try {
        const w = window.wb;
        if (!w?.user?.getXinfo || !w.user.getUserGrade || !w.user.setDiscountForUnAuth || !w.xnm?.getXnmProducts)
            fail('Изменилась схема runtime WB');
        // Share profile/wallet initialization, never a whole-product lock.
        const wallet = globalThis.__priceWatchWbWallet ??= {
            generation: globalThis.__priceWatchWbWalletStarting(), promise: null
        };
        if (!wallet.promise) wallet.promise = (async () => {
            const generation = await wallet.generation;
            await prepareProfile(w);
            await prepareWallet(w);
            return generation;
        })().finally(async () => {
            if (globalThis.__priceWatchWbWallet === wallet) globalThis.__priceWatchWbWallet = null;
            await globalThis.__priceWatchWbWalletFinished(await wallet.generation);
        });
        // Register ownership before waiting for bootstrap, including its failure
        // path. Python releases it only after response inspection/abort settles.
        const walletGeneration = await wallet.generation;
        await globalThis.__priceWatchWbWalletJoined(id, walletGeneration);
        await Promise.race([wallet.promise, new Promise((_, reject) => {
            if (controller.signal.aborted) reject(controller.signal.reason);
            else controller.signal.addEventListener('abort', () => reject(controller.signal.reason), {once: true});
        })]);
        if (controller.signal.aborted) fail('WB: таймаут условий');
        const products = await waitNative(w.xnm.getXnmProducts([Number(nmId)], true, false, null, null, false, controller.signal));
        const matches = Object.values(products ?? {}).filter(p => String(p?.id) === nmId);
        if (matches.length !== 1) fail('WB: ответ не содержит выбранный товар');
        const p = matches[0];
        if (!Array.isArray(p.sizes)) fail('WB: отсутствуют размеры');
        const sizes = p.sizes.map(s => ({
            optionId: safeId(s.optionId), name: s.name ?? '', origName: s.origName ?? '',
            stocks: s.stocks?.map(stock => ({qty: stock.qty})),
            price: s.price ? {
                priceToShow: money(s.price.priceToShow, true),
                paymentDiscountAmount: money(s.price.paymentDiscountAmount)
            } : null
        }));
        let imageUrl = null;
        // Use the storefront's current basket routing and AB photo selection.
        // Both helpers are synchronous; missing optional image data cannot stall price collection.
        if (Number.isInteger(p.pics) && p.pics > 0 &&
            typeof w.helpers?.url?.urlProductStatic === 'function' &&
            typeof w.helpers.getCardImgName === 'function') {
            try {
                const base = new URL(w.helpers.url.urlProductStatic(Number(nmId)));
                const photo = w.helpers.getCardImgName({nmId: Number(nmId), viewFlags: p.viewFlags, idx: 1});
                if (base.protocol === 'https:' && /\/info\/[^/]+\/card\.json$/.test(base.pathname) &&
                    /^(?:[1-9][0-9]*|ab_[0-9]+)$/.test(String(photo))) {
                    base.pathname = base.pathname.replace(/\/info\/[^/]+\/card\.json$/, `/images/big/${photo}.webp`);
                    base.search = '';
                    base.hash = '';
                    imageUrl = base.href;
                }
            } catch { /* Images are optional; never replace an exact price with an image error. */ }
        }
        let metadata = null;
        if (typeof w.xnm.getProductColorsByNmIdsAsync === 'function') {
            try {
                if (controller.signal.aborted) throw controller.signal.reason;
                const all = await waitNative(w.xnm.getProductColorsByNmIdsAsync([Number(nmId)]));
                const m = all?.[nmId];
                if (m) metadata = {options: m.options ?? (m.c ? [{name: 'Цвет', value: m.c}] : []), description: m.description};
            } catch (error) {
                if (error?.unsafe) throw error;
                /* Metadata is optional; price and size are already exact. */
            }
        }
        return {currency: 'RUB', walletReady: true, walletGeneration, product: {
            id: safeId(p.id), name: p.name, brand: p.brand, supplier: p.supplier,
            supplierId: p.supplierId == null ? null : safeId(p.supplierId),
            reviewRating: p.reviewRating, feedbacks: p.feedbacks, imageUrl, sizes
        }, metadata};
    } catch (error) {
        return {errorKind: error?.unsafe ? 'unsafe' : controller.signal.aborted ? 'timeout' : 'schema', error: controller.signal.aborted ? 'Таймаут запроса WB' : String(error?.message ?? error ?? 'неизвестная ошибка WB')};
    } finally {
        network.owners.delete(nmId);
        registry.delete(id);
        finished();
    }
}
