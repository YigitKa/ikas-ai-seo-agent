import io
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import customtkinter as ctk
import httpx
from PIL import Image

ImageCallback = Callable[[Image.Image], None]
ErrorCallback = Optional[Callable[[], None]]


class ImageService:
    """Shared downloader/cache for resized product images."""

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=15, follow_redirects=True)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="images")
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, tuple[int, int]], Image.Image | None] = {}
        self._pending: dict[
            tuple[str, tuple[int, int]],
            list[tuple[ctk.CTkBaseClass, ImageCallback, ErrorCallback]],
        ] = {}

    def load(
        self,
        url: str,
        size: tuple[int, int],
        widget: ctk.CTkBaseClass,
        on_success: ImageCallback,
        on_error: ErrorCallback = None,
    ) -> None:
        key = (url, size)

        with self._lock:
            cached = self._cache.get(key)
            if key in self._cache:
                self._dispatch(widget, cached, on_success, on_error)
                return

            waiters = self._pending.setdefault(key, [])
            waiters.append((widget, on_success, on_error))
            if len(waiters) > 1:
                return

        self._executor.submit(self._fetch, key)

    def _fetch(self, key: tuple[str, tuple[int, int]]) -> None:
        url, size = key
        image: Image.Image | None = None

        try:
            response = self._client.get(url)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content)).convert("RGBA")
            image.thumbnail(size, Image.LANCZOS)
        except Exception:
            image = None

        with self._lock:
            self._cache[key] = image.copy() if image is not None else None
            waiters = self._pending.pop(key, [])

        for widget, on_success, on_error in waiters:
            self._dispatch(widget, image, on_success, on_error)

    def _dispatch(
        self,
        widget: ctk.CTkBaseClass,
        image: Image.Image | None,
        on_success: ImageCallback,
        on_error: ErrorCallback,
    ) -> None:
        try:
            if image is None:
                if on_error is not None:
                    widget.after(0, on_error)
                return

            widget.after(0, lambda img=image.copy(): on_success(img))
        except Exception:
            return


_image_service = ImageService()


def get_image_service() -> ImageService:
    return _image_service
