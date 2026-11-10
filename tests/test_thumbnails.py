import asyncio
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image, ImageDraw

from price_watch.ports.thumbnails import MAX_THUMBNAIL_SIZE, THUMBNAIL_BOXES

from price_watch.infrastructure.thumbnails import (
    Download, ThumbnailError, ThumbnailService, render_thumbnail, public_address,
    download_image, FRESH_SECONDS, MAX_INPUT,
)


def photo(size=(600, 800), color='white'):
    image = Image.new('RGB', size, color)
    draw = ImageDraw.Draw(image)
    draw.line((0, 0, size[0], size[1]), fill='black', width=3)
    stream = BytesIO()
    image.save(stream, format='JPEG')
    return stream.getvalue()


class ThumbnailTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.source = photo()
        self.downloader = AsyncMock(return_value=Download(self.source, 'v1', 'date'))
        self.service = ThumbnailService(self.directory, downloader=self.downloader)

    def test_recipe_pixels_dimensions_and_small_images(self):
        for size in (68, 85, 102, 136, 204):
            with Image.open(BytesIO(self.source)) as image:
                expected = image.copy()
            expected.thumbnail((size, size), Image.Resampling.LANCZOS, reducing_gap=2.0)
            with Image.open(BytesIO(render_thumbnail(self.source, (size, size)))) as result:
                self.assertEqual(result.format, 'PNG')
                self.assertEqual(result.size, (size, size))
                x, y = (size - expected.width) // 2, (size - expected.height) // 2
                self.assertEqual(result.crop((x, y, x + expected.width, y + expected.height)).tobytes(), expected.convert('RGBA').tobytes())
                self.assertEqual(result.getpixel((0, 0))[3], 0)
        with Image.open(BytesIO(render_thumbnail(photo((30, 40)), (68, 68)))) as result:
            self.assertEqual(result.size, (68, 68))
            self.assertEqual(result.getchannel('A').getbbox(), (19, 14, 49, 54))
        for size in (0, MAX_THUMBNAIL_SIZE + 1):
            with self.assertRaises(ThumbnailError):
                render_thumbnail(self.source, (size, size))

    def test_portrait_profiles_preserve_photo_and_transparent_padding(self):
        self.assertEqual(THUMBNAIL_BOXES, {'list': (51, 68), 'tile': (276, 368), 'detail': (384, 512)})
        for size in THUMBNAIL_BOXES.values():
            with Image.open(BytesIO(render_thumbnail(photo((800, 600)), size))) as image:
                self.assertEqual(image.size, size)
                self.assertEqual(image.width * 4, image.height * 3)
                left, top, right, bottom = image.getchannel('A').getbbox()
                self.assertEqual((left, right), (0, size[0]))
                self.assertGreater(top, 0)
                self.assertAlmostEqual((bottom - top) / (right - left), .75, delta=.02)

    async def test_sizes_have_separate_persistent_cache_entries(self):
        small = await self.service.get('https://cdn.test/a', (68, 68))
        large = await self.service.get('https://cdn.test/a', (136, 136))
        self.assertNotEqual(small, large)
        restarted = ThumbnailService(self.directory, downloader=self.downloader)
        self.assertEqual(await restarted.get('https://cdn.test/a', (68, 68)), small)
        self.assertEqual(await restarted.get('https://cdn.test/a', (136, 136)), large)
        self.assertEqual(self.downloader.await_count, 1)

    async def test_singleflight_restart_and_source_change(self):
        results = await asyncio.gather(*(self.service.get('https://cdn.test/a', (68, 68)) for _ in range(20)))
        self.assertTrue(all(item == results[0] for item in results))
        self.downloader.assert_awaited_once()
        restarted = ThumbnailService(self.directory, downloader=self.downloader)
        self.assertEqual(await restarted.get('https://cdn.test/a', (68, 68)), results[0])
        self.downloader.assert_awaited_once()
        await restarted.get('https://cdn.test/b', (68, 68))
        self.assertEqual(self.downloader.await_count, 2)

    async def test_cancelled_request_does_not_cancel_shared_job(self):
        ready, release = asyncio.Event(), asyncio.Event()
        async def download(*args):
            ready.set()
            await release.wait()
            return Download(self.source)
        self.service.downloader = download
        first = asyncio.create_task(self.service.get('https://cdn.test/a', (68, 68)))
        await ready.wait()
        second = asyncio.create_task(self.service.get('https://cdn.test/a', (68, 68)))
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        release.set()
        self.assertTrue((await second).startswith(b'\x89PNG'))

    async def test_concurrency_is_two_for_different_urls(self):
        active = maximum = 0
        async def download(*args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(.01)
            active -= 1
            return Download(self.source)
        self.service.downloader = download
        await asyncio.gather(*(self.service.get(f'https://cdn.test/{i}', (68, 68)) for i in range(12)))
        self.assertEqual(maximum, 2)

    async def test_revalidation_304_and_same_content_skip_render(self):
        now = [100.0]
        self.service.clock = lambda: now[0]
        expected = await self.service.get('https://cdn.test/a', (68, 68))
        now[0] += FRESH_SECONDS + 1
        self.downloader.return_value = Download(None)
        with patch('price_watch.infrastructure.thumbnails.render_thumbnail', side_effect=AssertionError('rendered twice')):
            self.assertEqual(await self.service.get('https://cdn.test/a', (68, 68)), expected)
            now[0] += FRESH_SECONDS + 1
            self.downloader.return_value = Download(self.source)
            self.assertEqual(await self.service.get('https://cdn.test/a', (68, 68)), expected)
        self.assertEqual(self.downloader.call_args_list[1].args[1]['etag'], 'v1')
        now[0] += FRESH_SECONDS + 1
        self.downloader.return_value = Download(photo(color='red'))
        self.assertNotEqual(await self.service.get('https://cdn.test/a', (68, 68)), expected)

    async def test_error_cache_limits_and_corrupt_cache(self):
        self.downloader.return_value = Download(b'bad image')
        for _ in range(2):
            with self.assertRaises(ThumbnailError):
                await self.service.get('https://cdn.test/bad', (68, 68))
        self.downloader.assert_awaited_once()
        with self.assertRaises(ThumbnailError):
            render_thumbnail(b'x' * (MAX_INPUT + 1), (68, 68))
        with patch('price_watch.infrastructure.thumbnails.MAX_PIXELS', 10):
            with self.assertRaises(ThumbnailError):
                render_thumbnail(self.source, (68, 68))
        self.downloader.return_value = Download(self.source)
        await self.service.get('https://cdn.test/a', (68, 68))
        next((self.directory / 'sources').glob('*.json')).write_text('bad metadata')
        for path in self.directory.glob('*.json'):
            path.write_text('bad metadata')
        await self.service.get('https://cdn.test/a', (68, 68))
        self.assertEqual(self.downloader.await_count, 3)

    async def test_lru_only_removes_own_files(self):
        sentinel = self.directory / 'user.png'
        sentinel.write_bytes(b'keep')
        first = await self.service.get('https://cdn.test/a', (68, 68))
        self.service.max_bytes = 2 * (len(first) + 300)
        await self.service.get('https://cdn.test/b', (68, 68))
        self.assertEqual(sentinel.read_bytes(), b'keep')
        self.assertEqual(len(list(self.directory.glob('*.json'))), 1)
        self.assertEqual(len(list(self.directory.glob('*.tmp'))), 0)

    async def test_public_address_rejects_unsafe_schemes_and_dns(self):
        resolver = AsyncMock(return_value=[(0,0,0,'',('127.0.0.1',443))])
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', resolver):
            for url in ['http://cdn.test/a', 'https://localhost/a', 'https://cdn.test:123/a', 'https://u:p@cdn.test/a']:
                with self.assertRaises(ThumbnailError):
                    await public_address(httpx.URL(url))
            resolver.return_value = [(0,0,0,'',('93.184.216.34',443))]
            self.assertEqual(await public_address(httpx.URL('https://cdn.test/a')), '93.184.216.34')
            resolver.return_value.append((0,0,0,'',('10.0.0.1',443)))
            with self.assertRaises(ThumbnailError):
                await public_address(httpx.URL('https://cdn.test/a'))

    async def test_fake_ip_is_allowed_only_for_marketplace_cdn_domains(self):
        resolver = AsyncMock()
        with patch.object(asyncio.get_running_loop(), 'getaddrinfo', resolver):
            for address in ('198.18.0.0', '198.18.0.7', '198.19.255.255'):
                resolver.return_value = [(0, 0, 0, '', (address, 443))]
                for host in ('ozone.ru', 'ir.ozone.ru', 'ir-27.ozone.ru',
                             'basket-04.wbbasket.ru', 'ae-pic-a1.aliexpress-media.com',
                             'avatars.mds.yandex.net'):
                    with self.subTest(host=host, address=address):
                        self.assertEqual(await public_address(httpx.URL(f'https://{host}/a')), address)
                for host in ('cdn.test', 'fakeozone.ru', 'ozone.ru.attacker.test',
                             'wbbasket.ru.attacker.test', 'fakealiexpress-media.com',
                             'fakeavatars.mds.yandex.net', 'avatars.mds.yandex.net.attacker.test',
                             'market.yandex.ru', address):
                    with self.subTest(host=host, address=address), self.assertRaises(ThumbnailError):
                        await public_address(httpx.URL(f'https://{host}/a'))
            for address in ('127.0.0.1', '10.0.0.1', '169.254.169.254', '192.168.1.1',
                            '::1', 'fc00::1', '::ffff:127.0.0.1', '224.0.0.1'):
                resolver.return_value = [(0, 0, 0, '', ('198.18.0.7', 443)),
                                         (0, 0, 0, '', (address, 443))]
                with self.subTest(address=address), self.assertRaises(ThumbnailError):
                    await public_address(httpx.URL('https://ir.ozone.ru/a'))

    async def test_fake_ip_download_preserves_tls_name_and_rechecks_redirects(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(302, headers={'location': 'https://ozone.ru.attacker.test/a'})
        original = httpx.AsyncClient
        dns = AsyncMock(return_value=[(0, 0, 0, '', ('198.18.0.7', 443))])
        with (patch.object(asyncio.get_running_loop(), 'getaddrinfo', dns),
              patch('price_watch.infrastructure.thumbnails.httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw))):
            with self.assertRaises(ThumbnailError):
                await download_image('https://ir.ozone.ru/a', {})
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), 'https://198.18.0.7/a')
        self.assertEqual(requests[0].headers['host'], 'ir.ozone.ru')
        self.assertEqual(requests[0].extensions['sni_hostname'], 'ir.ozone.ru')
        self.assertEqual(dns.await_count, 2)

    async def test_download_pins_ip_sni_headers_and_checks_redirects(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(302, headers={'location': 'https://127.0.0.1/private'})
        original = httpx.AsyncClient
        resolver = AsyncMock(side_effect=['93.184.216.34', ThumbnailError('private')])
        with (patch('price_watch.infrastructure.thumbnails.public_address', resolver),
              patch('price_watch.infrastructure.thumbnails.httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(respond), **kw))):
            with self.assertRaises(ThumbnailError):
                await download_image('https://cdn.test/a', {})
        self.assertEqual(str(requests[0].url), 'https://93.184.216.34/a')
        self.assertEqual(requests[0].headers['host'], 'cdn.test')
        self.assertEqual(requests[0].extensions['sni_hostname'], 'cdn.test')
        self.assertNotIn('x-price-watch-token', requests[0].headers)
        self.assertEqual(resolver.await_count, 2)

    async def test_download_size_timeout_and_conditional_headers(self):
        original = httpx.AsyncClient
        for response in (httpx.Response(200, headers={'content-length': str(MAX_INPUT+1)}),
                         httpx.Response(200, content=b'x'*(MAX_INPUT+1))):
            with (patch('price_watch.infrastructure.thumbnails.public_address', AsyncMock(return_value='93.184.216.34')),
                  patch('price_watch.infrastructure.thumbnails.httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(lambda req: response), **kw))):
                with self.assertRaises(ThumbnailError):
                    await download_image('https://cdn.test/a', {})
        def unchanged(request):
            self.assertEqual(request.headers['if-none-match'], 'v1')
            return httpx.Response(304)
        with (patch('price_watch.infrastructure.thumbnails.public_address', AsyncMock(return_value='93.184.216.34')),
              patch('price_watch.infrastructure.thumbnails.httpx.AsyncClient', side_effect=lambda **kw: original(transport=httpx.MockTransport(unchanged), **kw))):
            self.assertIsNone((await download_image('https://cdn.test/a', {'etag':'v1'})).content)
        # The total deadline also includes DNS, before any network connection.
        async def slow(*args):
            await asyncio.sleep(.1)
        timeout = asyncio.timeout
        with (patch('price_watch.infrastructure.thumbnails.public_address', slow),
              patch('price_watch.infrastructure.thumbnails.asyncio.timeout', side_effect=lambda _: timeout(.001))):
            with self.assertRaises(TimeoutError):
                await download_image('https://cdn.test/a', {})
