"""Reading and writing the Wayland clipboard through wl-clipboard."""
from __future__ import annotations

import os
import shutil
import subprocess
import time

from .transforms import Clip

TEXT_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "STRING", "TEXT")


def _env() -> dict[str, str]:
    e = dict(os.environ)
    e.setdefault("WAYLAND_DISPLAY", "wayland-1")
    return e


def _run(cmd: list[str], data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=data, capture_output=True, env=_env(), check=False)


def _copy(cmd: list[str], data: bytes) -> None:
    """wl-copy, which forks a daemon to serve the selection until someone else claims it.

    That daemon inherits whatever stdout and stderr it was given and keeps them open
    for as long as it owns the clipboard, so capturing them would hang here forever
    waiting for an EOF that only arrives when the user copies something else. Send
    both to /dev/null and let it go.
    """
    with open(os.devnull, "wb") as null:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=null, stderr=null, env=_env())
        p.communicate(data)


def available() -> bool:
    return shutil.which("wl-paste") is not None and shutil.which("wl-copy") is not None


def types() -> list[str]:
    r = _run(["wl-paste", "--list-types"])
    return r.stdout.decode(errors="replace").split() if r.returncode == 0 else []


def read_type(mime: str) -> bytes | None:
    r = _run(["wl-paste", "--no-newline", "--type", mime])
    return r.stdout if r.returncode == 0 else None


def read() -> Clip:
    have = types()
    text = ""
    for mime in TEXT_TYPES:
        if mime in have or not have:
            raw = read_type(mime)
            if raw:
                text = raw.decode("utf-8", "replace")
                break
    html = None
    if "text/html" in have:
        raw = read_type("text/html")
        if raw:
            html = raw.decode("utf-8", "replace")
    return Clip(text=text, html=html)


def read_image() -> tuple[str, bytes] | None:
    """The clipboard's image, as (extension, bytes)."""
    for mime, ext in (("image/png", "png"), ("image/jpeg", "jpg"), ("image/webp", "webp")):
        if mime in types():
            raw = read_type(mime)
            if raw:
                return ext, raw
    return None


def write(text: str, mime: str = "text/plain;charset=utf-8") -> None:
    _copy(["wl-copy", "--type", mime], text.encode("utf-8"))


def write_uri_list(paths: list[str]) -> None:
    data = "\r\n".join("file://" + p for p in paths) + "\r\n"
    _copy(["wl-copy", "--type", "text/uri-list"], data.encode("utf-8"))


def paste_into_focused() -> bool:
    """Send Shift+Insert, the paste that works in terminals and everywhere else.

    Omarchy's own clipboard scripts use exactly this; the short sleep gives the
    menu overlay time to close and hand focus back to the window underneath.
    """
    if shutil.which("wtype") is None:
        return False
    time.sleep(0.15)
    r = _run(["wtype", "-M", "shift", "-k", "Insert", "-m", "shift"])
    return r.returncode == 0
