"""Thread-safe tkinter GUI runner.

Runs tkinter code in a dedicated daemon thread so it doesn't block the
async event loop.  Only one GUI window is allowed at a time (mutex).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_gui_lock = threading.Lock()
_GUI_TIMEOUT = 300  # 5 minutes


async def run_in_gui_thread(fn: Callable[..., T], *args: Any, timeout: float = _GUI_TIMEOUT) -> T | None:
    """Execute *fn* inside a daemon thread with its own Tk root.

    Only one GUI invocation is allowed at a time.  If the timeout expires
    the result is ``None``.
    """
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T | None] = loop.create_future()

    def _worker() -> None:
        acquired = _gui_lock.acquire(timeout=5)
        if not acquired:
            loop.call_soon_threadsafe(future.set_result, None)
            return

        try:
            import tkinter as tk

            # Create a hidden root if fn doesn't build one itself
            _root = tk.Tk()
            _root.withdraw()

            result = fn(*args)

            try:
                _root.destroy()
            except Exception:
                pass

            if not future.done():
                loop.call_soon_threadsafe(future.set_result, result)
        except Exception as exc:
            logger.exception("GUI thread error: %s", exc)
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, None)
        finally:
            _gui_lock.release()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except TimeoutError:
        logger.warning("GUI timed out after %ss", timeout)
        return None
