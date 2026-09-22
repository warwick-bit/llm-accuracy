"""Inspect host metadata only; never parse file contents or shell output."""

from __future__ import annotations


def builtin_codes(tool: str, response: object) -> set[str]:
    if not isinstance(response, dict):
        return set()
    if tool == "Bash":
        path = response.get("persistedOutputPath")
        size = response.get("persistedOutputSize")
        stdout = response.get("stdout")
        # Host sizes are bytes; comparing character counts would misclassify Unicode.
        if (
            isinstance(path, str)
            and path
            and type(size) is int
            and isinstance(stdout, str)
        ):
            if size > len(stdout.encode("utf-8", errors="replace")):
                return {"bash_output_excerpt"}
    if tool == "Read" and response.get("type") == "text":
        file = response.get("file")
        if not isinstance(file, dict):
            return set()
        start, count, total = (
            file.get(k) for k in ("startLine", "numLines", "totalLines")
        )
        if all(type(value) is int for value in (start, count, total)):
            if start >= 1 and 0 <= count <= total and (start > 1 or count < total):
                return {"file_read_excerpt"}
    return set()


BUILTIN_ADVICE = (
    "PARTIAL RESULT SIGNAL: {codes}. The host reports an excerpt: a selected file "
    "line range or shell output shorter than its saved output. An intentional excerpt "
    "is not a failed read. Limit claims to the portion inspected; read the relevant "
    "remaining lines or saved output before making whole-file or full-output claims. "
    "Do not infer project-wide coverage or completeness from silence. "
    "This check keeps no state. Mute with `{env}=1`."
)
