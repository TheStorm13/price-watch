async ({id, nmId, timeoutMs}) => {
    const registry = globalThis.__priceWatchWbRequests ??= new Map();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let finished;
    const done = new Promise(resolve => { finished = resolve; });
    registry.set(id, {controller, done});
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
        while (!controller.signal.aborted) {
            try {
                const xinfo = await w.user.getXinfo();
                if (typeof xinfo === 'string' && xinfo.length > 0) {
                    profileReady = true;
                    break;
                }
            } catch { /* The host may still be initializing. */ }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        if (!profileReady) fail('WB: контекст профиля не готов');
        if (w.user.getCurrency() !== 'RUB') fail('WB: требуется валюта RUB');
    };
    const fresh = value => Number.isFinite(value) && value > Date.now();
    const validPercent = value => Number.isFinite(value) && value >= 0 && value <= 100;
    const prepareWallet = async w => {
        // getUserGrade is auth-aware and returns null for an anonymous profile.
        const grade = await w.user.getUserGrade('RUB');
        if (grade === null) {
            await w.user.setDiscountForUnAuth();
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
        await prepareProfile(w);
        await prepareWallet(w);
        if (controller.signal.aborted) fail('WB: таймаут условий');
        const products = await w.xnm.getXnmProducts([Number(nmId)], true, false, null, null, false, controller.signal);
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
        let metadata = null;
        let metadataTimedOut = false;
        if (typeof w.xnm.getProductColorsByNmIdsAsync === 'function') {
            try {
                let metadataTimer;
                const all = await Promise.race([
                    w.xnm.getProductColorsByNmIdsAsync([Number(nmId)]),
                    new Promise(resolve => { metadataTimer = setTimeout(() => {
                        metadataTimedOut = true; resolve(null);
                    }, Math.min(3000, timeoutMs / 3)); })
                ]).finally(() => clearTimeout(metadataTimer));
                const m = all?.[nmId];
                if (m) metadata = {options: m.options ?? (m.c ? [{name: 'Цвет', value: m.c}] : []), description: m.description};
            } catch { /* Metadata is optional; price and size are already exact. */ }
        }
        return {currency: 'RUB', walletReady: true, product: {
            id: safeId(p.id), name: p.name, brand: p.brand, supplier: p.supplier,
            supplierId: p.supplierId == null ? null : safeId(p.supplierId),
            reviewRating: p.reviewRating, feedbacks: p.feedbacks, sizes
        }, metadata, metadataTimedOut};
    } catch (error) {
        return {errorKind: controller.signal.aborted ? 'timeout' : 'schema', error: controller.signal.aborted ? 'Таймаут запроса WB' : String(error.message)};
    } finally {
        clearTimeout(timer);
        registry.delete(id);
        finished();
    }
}
