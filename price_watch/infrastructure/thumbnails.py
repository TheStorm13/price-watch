"""Recoverable, bounded cache of catalog row images. No database writes."""
import asyncio
from dataclasses import dataclass
import hashlib
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import time
import uuid
import warnings

import httpx
from PIL import Image

from ..domain.errors import ThumbnailError

RECIPE = "pillow-13-lanczos-204-png-v1"
MAX_INPUT = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
CACHE_BYTES = 256 * 1024 * 1024
FRESH_SECONDS = 24 * 60 * 60
ERROR_SECONDS = 30
_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
_FAKE_IP_CDN_DOMAINS = ("ozone.ru", "wbbasket.ru", "aliexpress-media.com")
_OWN_FILE = re.compile(r"[0-9a-f]{64}\.(png|json)$")


@dataclass(frozen=True)
class Download:
    content: bytes | None
    etag: str | None = None
    modified: str | None = None


async def public_address(url: httpx.URL) -> str:
    if url.scheme != "https" or not url.host or url.userinfo or url.port not in (None, 443):
        raise ThumbnailError("Недопустимый адрес изображения")
    addresses = await asyncio.get_running_loop().getaddrinfo(
        url.host, 443, type=socket.SOCK_STREAM,
    )
    ips = {entry[4][0] for entry in addresses}
    # Local DNS routing can represent a public CDN with a synthetic address.
    # Permit only this range for known CDN domains, retaining Host/SNI validation.
    host = url.host.rstrip(".").lower()
    allow_fake_ip = any(host == domain or host.endswith(f".{domain}") for domain in _FAKE_IP_CDN_DOMAINS)
    parsed = [ipaddress.ip_address(ip) for ip in ips]
    if not parsed or any(
        ip.is_multicast or not (ip.is_global or (allow_fake_ip and ip in _FAKE_IP_NETWORK))
        for ip in parsed
    ):
        raise ThumbnailError("Недопустимый сетевой адрес изображения")
    return sorted(ips)[0]


async def download_image(url: str, metadata: dict) -> Download:
    # Pin each connection to a checked IP. Host + SNI retain certificate validation;
    # no second hostname resolution, environment proxy, cookies or API credentials.
    async with asyncio.timeout(15):
        async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=15) as client:
            target = httpx.URL(url)
            for _ in range(6):
                address = await public_address(target)
                headers = {"Host": target.host, "Accept-Encoding": "identity"}
                if metadata.get("etag"):
                    headers["If-None-Match"] = metadata["etag"]
                if metadata.get("modified"):
                    headers["If-Modified-Since"] = metadata["modified"]
                async with client.stream(
                    "GET", target.copy_with(host=address), headers=headers,
                    extensions={"sni_hostname": target.host},
                ) as response:
                    if response.status_code == 304:
                        if not metadata:
                            raise ThumbnailError("Неожиданный ответ источника")
                        return Download(None, response.headers.get("etag"), response.headers.get("last-modified"))
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ThumbnailError("Редирект без адреса")
                        target = target.join(location)
                        continue
                    response.raise_for_status()
                    if int(response.headers.get("content-length", "0")) > MAX_INPUT:
                        raise ThumbnailError("Изображение слишком большое")
                    content = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        content.extend(chunk)
                        if len(content) > MAX_INPUT:
                            raise ThumbnailError("Изображение слишком большое")
                    return Download(bytes(content), response.headers.get("etag"), response.headers.get("last-modified"))
            raise ThumbnailError("Слишком много редиректов")


def render_thumbnail(content: bytes) -> bytes:
    if len(content) > MAX_INPUT:
        raise ThumbnailError("Изображение слишком большое")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ThumbnailError("Слишком много пикселей")
            # Load at full resolution before thumbnail, as in the selected experiment.
            # In particular, do not let JPEG draft change the resampling input.
            thumbnail = image.copy()
        if thumbnail.mode not in ("RGB", "RGBA", "L", "LA"):
            thumbnail = thumbnail.convert("RGBA" if "transparency" in thumbnail.info else "RGB")
        thumbnail.thumbnail((204, 204), Image.Resampling.LANCZOS, reducing_gap=2.0)
        output = BytesIO()
        thumbnail.save(output, format="PNG")
        return output.getvalue()


class ThumbnailService:
    def __init__(self, directory: Path | None = None, *, downloader=download_image,
                 max_bytes: int = CACHE_BYTES, clock=time.time):
        self.directory = directory if directory is not None else (
            Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "price-watch" / "thumbnails"
        )
        self.downloader = downloader
        self.max_bytes = max_bytes
        self.clock = clock
        self._slots = asyncio.Semaphore(2)
        self._tasks: dict[str, asyncio.Task] = {}
        self._errors: dict[str, float] = {}
        self._disk_lock = asyncio.Lock()

    async def get(self, url: str) -> bytes:
        key = hashlib.sha256(f"{RECIPE}\n{url}".encode()).hexdigest()
        if self._errors.get(key, 0) > self.clock():
            raise ThumbnailError("Источник изображения временно недоступен")
        task = self._tasks.get(key)
        if task is None:
            task = asyncio.create_task(self._produce(key, url))
            self._tasks[key] = task
            task.add_done_callback(lambda done: self._finished(key, done))
        # A scrolled-away row must not cancel work shared by another row.
        return await asyncio.shield(task)

    def _finished(self, key, task):
        self._tasks.pop(key, None)
        if not task.cancelled():
            task.exception()  # Retrieve errors even when every requester disconnected.

    async def close(self):
        await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)

    async def _produce(self, key: str, url: str) -> bytes:
        try:
            async with self._slots:
                async with self._disk_lock:
                    cached = await asyncio.to_thread(self._read, key)
                if cached and self.clock() - cached[1]["checked"] < FRESH_SECONDS:
                    return cached[0]
                metadata = cached[1] if cached else {}
                downloaded = await self.downloader(url, metadata)
                if downloaded.content is None:
                    if cached is None:
                        raise ThumbnailError("Нет сохранённого изображения")
                    png, digest = cached[0], metadata["digest"]
                else:
                    digest = hashlib.sha256(downloaded.content).hexdigest()
                    png = cached[0] if cached and digest == metadata["digest"] else await asyncio.to_thread(render_thumbnail, downloaded.content)
                metadata = {
                    "checked": self.clock(), "digest": digest,
                    "png_digest": hashlib.sha256(png).hexdigest(),
                    "etag": downloaded.etag or (metadata.get("etag") if downloaded.content is None else None),
                    "modified": downloaded.modified or (metadata.get("modified") if downloaded.content is None else None),
                }
                async with self._disk_lock:
                    await asyncio.to_thread(self._write, key, png, metadata)
                self._errors.pop(key, None)
                return png
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            now = self.clock()
            self._errors = {key: until for key, until in self._errors.items() if until > now}
            self._errors[key] = now + ERROR_SECONDS
            raise ThumbnailError("Не удалось подготовить миниатюру") from exc

    def _read(self, key):
        try:
            png = self.directory / f"{key}.png"
            metadata = json.loads((self.directory / f"{key}.json").read_text())
            content = png.read_bytes()
            if (hashlib.sha256(content).hexdigest() != metadata["png_digest"]
                    or not isinstance(metadata["checked"], (int, float)) or not metadata["digest"]):
                return None
            os.utime(png, None)
            return content, metadata
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write(self, key, png, metadata):
        self.directory.mkdir(parents=True, exist_ok=True)
        for suffix, content in (("png", png), ("json", json.dumps(metadata).encode())):
            destination = self.directory / f"{key}.{suffix}"
            temporary = self.directory / f".{key}.{uuid.uuid4().hex}.tmp"
            try:
                with temporary.open("xb") as stream:
                    stream.write(content)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        groups: dict[str, tuple[float, list[Path]]] = {}
        total = 0
        for path in self.directory.iterdir():
            if not _OWN_FILE.fullmatch(path.name) or not path.is_file() or path.is_symlink():
                continue
            stat = path.stat()
            total += stat.st_size
            last_used, paths = groups.get(path.stem, (0, []))
            paths.append(path)
            groups[path.stem] = max(last_used, stat.st_mtime), paths
        # Group by key so interrupted writes (orphan PNG/JSON) are bounded too.
        for _, paths in sorted(groups.values(), key=lambda group: group[0]):
            if total <= self.max_bytes:
                break
            for path in paths:
                total -= path.stat().st_size
                path.unlink()
