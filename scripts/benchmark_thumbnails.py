"""100 synthetic local JPEGs; no marketplace, database or persistent user cache.

Run: .venv/bin/python -m scripts.benchmark_thumbnails
"""
import asyncio
from io import BytesIO
import json
from pathlib import Path
import platform
import tempfile
import time
from unittest.mock import patch

from PIL import Image, ImageDraw, __version__ as pillow_version
from price_watch.infrastructure.thumbnails import Download, ThumbnailService, render_thumbnail


async def main():
    with tempfile.TemporaryDirectory(prefix='price-watch-thumbnails-') as directory:
        root = Path(directory)
        sources = root / 'sources'
        sources.mkdir()
        base = Image.effect_noise((1800, 2400), 50).convert('RGB')
        for index in range(100):
            image = base.copy()
            ImageDraw.Draw(image).rectangle((20, 20, 300, 300), fill=(index*2, 100, 200))
            image.save(sources / f'{index}.jpg', quality=90)
        calls = 0
        async def download(url, metadata):
            nonlocal calls
            calls += 1
            return Download(await asyncio.to_thread((sources / f'{url.rsplit("/", 1)[1]}.jpg').read_bytes))
        urls = [f'https://synthetic.test/{index}' for index in range(100)]
        cache = root / 'cache'
        results = {}
        for phase in ('cold', 'warm_after_restart'):
            service = ThumbnailService(cache, downloader=download)
            before_calls = calls
            with patch('price_watch.infrastructure.thumbnails.render_thumbnail', wraps=render_thumbnail) as render:
                wall, cpu = time.perf_counter(), time.process_time()
                images = await asyncio.gather(*(service.get(url, (68, 68)) for url in urls))
                results[phase] = {'wall_seconds': round(time.perf_counter()-wall, 4),
                                  'cpu_seconds': round(time.process_time()-cpu, 4),
                                  'downloads': calls-before_calls, 'renders': render.call_count,
                                  'png_bytes': sum(map(len, images))}
            await service.close()
            assert len(images) == 100 and all(Image.open(BytesIO(data)).size == (68, 68) for data in images)
        assert results['warm_after_restart']['downloads'] == results['warm_after_restart']['renders'] == 0
        print(json.dumps({'python': platform.python_version(), 'pillow': pillow_version,
                          'source_size': [1800,2400], 'count':100, 'parallelism':2,
                          'network':'local fixture reads only; no simulated latency',
                          'results':results}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
