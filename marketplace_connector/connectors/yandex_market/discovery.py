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
    queue = deque((sku, root.links_may_include_other_models) for sku in root.edges)
    visited = {article}
    errors = []
    excluded = []
    if root.discovery_error:
        errors.append(root.discovery_error)
    while queue:
        sku, may_be_other_model = queue.popleft()
        if sku in visited:
            continue
        visited.add(sku)
        try:
            item = await fetch_product(sku)
            if item.parent_id != root.parent_id:
                # The storefront control can also link different models. They
                # are not variants of this card and cannot replace its article.
                if may_be_other_model:
                    excluded.append({'article': sku, 'product_id': item.parent_id, 'reason': 'different_product'})
                else:
                    errors.append(f'Маркет: другой parent product у SKU {sku}')
                continue
            found[sku] = item
            if item.discovery_error:
                errors.append(f'{sku}: {item.discovery_error}')
            queue.extend((neighbor, item.links_may_include_other_models) for neighbor in item.edges)
        except (AuthenticationRequired, UnsafeBrowserTeardown):
            raise
        except ConnectorError as exc:
            errors.append(f'{sku}: {exc}')
    for sku, item in found.items():
        variants = tuple(ProductVariant(v.card.ref, v.card.title, v.card.url, v.card.availability,
            selected=other == sku, options=v.options, image_url=v.card.image_url) for other, v in found.items())
        extensions = dict(item.card.extensions)
        if excluded:
            extensions['yandex_market'] = {**extensions['yandex_market'], 'excluded_variants': excluded}
        if errors:
            extensions['variant_discovery_error'] = '; '.join(dict.fromkeys(errors))
        snapshots[sku] = replace(item.card, variants=variants, extensions=extensions)


class FamilySession:
    """Coalesce by observed parent while keeping exact SKU reads independent."""
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
            task = self._task(self.families, root.parent_id, lambda: discover_family(
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
