"""Read the host UTF-8 protocol independently of the platform stdin codec."""

from __future__ import annotations

import io
from typing import TextIO


def read_hook_input(stream: TextIO, limit: int = -1) -> str:
    """Read once with a character cap; close no caller-owned stream.

    This consumes the hook input. Decoder read-ahead is not preserved for a
    second reader; every CLI calls this once, then exits.
    """
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream.read(limit)
    reader = io.TextIOWrapper(buffer, encoding="utf-8", errors="strict")
    try:
        return reader.read(limit)
    finally:
        reader.detach()
