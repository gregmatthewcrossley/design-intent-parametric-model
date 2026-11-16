"""Small file helpers shared by the intent store, the review record and proposals.

* `atomic_write`: temp file in the same directory + fsync + `os.replace`, so a reader
  (the GUI server, an editor, Claude) never sees a half-written file.
* `sha256_text` / `file_sha256`: the content hashes used for optimistic concurrency
  (every write carries the hash of the content it was based on; docs/user-experience.md §1.1).
"""
from __future__ import annotations

import hashlib
import os
import tempfile

_UMASK = os.umask(0)        # read once (os.umask can only be read by setting it)
os.umask(_UMASK)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: str | None) -> str | None:
    """sha256 of a file's bytes, or None if it does not exist."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def atomic_write(path: str, text: str | bytes) -> None:
    """Write `text` to `path` atomically (temp file in the same directory, then rename).
    Bytes are written as given; str is encoded as UTF-8 with no newline translation."""
    data = text.encode("utf-8") if isinstance(text, str) else text
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:     # mkstemp creates 0600: keep the old file's mode, else the usual umask default
            if os.path.exists(path):
                os.chmod(tmp, os.stat(path).st_mode & 0o777)
            else:
                os.chmod(tmp, 0o666 & ~_UMASK)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
