"""Traverse only declared storefront edges; retain verified prices on partial walks."""
import asyncio
from dataclasses import replace
from collections import deque

from ...domain.errors import ConnectorError, AuthenticationRequired, MarketplaceSchemaChanged, UnsafeBrowserTeardown
from ...domain.models import ProductVariant
from .parser import parse_product


async def discover_family(transport, article, snapshots, *, root=None, fetch_product=None):
    async def load(sku):
        return parse_product(await transport.fetch(sku), sku)
    fetch_product = fetch_product or load
    root = root or await fetch_product(article)
    found = {article: root}
    queue = deque((sku, root.has_structured_variants) for sku in root.edges)
    visited = {article}
    errors = []
    if root.discovery_error:
        errors.append(root.discovery_error)
    while queue:
        wave = []
        while queue:
            sku, storefront_variant = queue.popleft()
            if sku not in visited:
                visited.add(sku)
                wave.append((sku, storefront_variant))
        # The transport's shared pool controls admission, timeout and abort.
        # Read independent variant pages together instead of serializing RTTs.
        results = await asyncio.gather(*(fetch_product(sku) for sku, _ in wave), return_exceptions=True)
        for (sku, storefront_variant), item in zip(wave, results):
            if isinstance(item, (AuthenticationRequired, UnsafeBrowserTeardown)):
                raise item
            if isinstance(item, ConnectorError):
                errors.append(f'{sku}: {item}')
                continue
            if isinstance(item, BaseException):
                raise item
            if item.parent_id != root.parent_id and not storefront_variant:
                errors.append(f'Маркет: другой parent product у SKU {sku}')
                continue
            found[sku] = item
            if item.discovery_error:
                errors.append(f'{sku}: {item.discovery_error}')
            queue.extend((neighbor, item.has_structured_variants) for neighbor in item.edges)
    for sku, item in found.items():
        variants = tuple(ProductVariant(v.card.ref, v.card.title, v.card.url, v.card.availability,
            selected=other == sku, options=v.options, image_url=v.card.image_url) for other, v in found.items())
        extensions = dict(item.card.extensions)
        if errors:
            extensions['variant_discovery_error'] = '; '.join(dict.fromkeys(errors))
        snapshots[sku] = replace(item.card, variants=variants, extensions=extensions)


class FamilySession:
    """Coalesce declared variant groups while keeping exact article reads independent."""
    def __init__(self, transport):
        self.transport = transport
        self.nodes = {}
        self.families = {}
        self.snapshots = {}

    @staticmethod
    def _observe(task):
        if not task.cancelled():
            task.exception()

    def _task(self, cache, key, factory):
        previous = cache.get(key)
        if previous is not None and previous.done() and (previous.cancelled() or previous.exception()):
            cache.pop(key)
        if key not in cache:
            cache[key] = asyncio.create_task(factory())
            cache[key].add_done_callback(self._observe)
        return cache[key]

    async def load(self, sku):
        async def read():
            return parse_product(await self.transport.fetch(sku), sku)
        return await asyncio.shield(self._task(self.nodes, sku, read))

    async def get(self, sku):
        if sku not in self.snapshots:
            root = await self.load(sku)
            family_key = ('storefront', tuple(sorted(root.edges))) if root.has_structured_variants else ('product', root.parent_id)
            task = self._task(self.families, family_key, lambda: discover_family(
                self.transport, sku, self.snapshots, root=root, fetch_product=self.load))
            await asyncio.shield(task)
            if sku not in self.snapshots:
                raise MarketplaceSchemaChanged('Маркет: SKU отсутствует в подтверждённом семействе')
        return self.snapshots[sku]

    async def close(self):
        tasks = [*self.families.values(), *self.nodes.values()]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
