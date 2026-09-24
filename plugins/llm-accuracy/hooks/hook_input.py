"""Read the host UTF-8 protocol independently of the platform stdin codec."""

from __future__ import annotations

import io
from typing import TextIO


def read_hook_input(stream: TextIO, limit: int = -1) -> str:
    """Preserve character limits and leave the caller-owned binary stream open."""
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream.read(limit)
    reader = io.TextIOWrapper(buffer, encoding="utf-8", errors="strict")
    try:
        return reader.read(limit)
    finally:
        reader.detach()
