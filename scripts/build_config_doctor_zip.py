#!/usr/bin/env python3
"""Package the committed standalone Config Doctor without local audit outputs."""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile

from build_plugin_zip import tracked_plugin_files

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools/config-doctor"
VERSION = "0.1.1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "dist" / f"config-doctor-{VERSION}.zip")
    output = parser.parse_args().output
    files = tracked_plugin_files(SOURCE)
    if not files or not (SOURCE / "LICENSE").is_file():
        raise ValueError("committed Config Doctor source and licence required")
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("Config Doctor archive requires ordinary source files")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "config-doctor/" + path.relative_to(SOURCE).as_posix())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
