#!/usr/bin/env python3
"""
make-hf-mf-key-bin.py — synthesize a PM3 `hf-mf-<UID>-key.bin` key file
for use with `hf mf restore`. Key file format:

  Per sector (16 sectors for 1K):
    1 byte: number of keys (0, 1, or 2)
    0, 6, or 12 bytes: key bytes

Default to NXP factory transport keys (Key A A0A1A2A3A4A5, Key B B0B1B2B3B4B5)
when no source keys are provided.
"""

import sys
from pathlib import Path

KEY_A = bytes.fromhex("A0A1A2A3A4A5")
KEY_B = bytes.fromhex("B0B1B2B3B4B5")


def build(out_path: Path) -> None:
    with out_path.open("wb") as f:
        for _ in range(16):  # 16 sectors for 1K
            f.write(KEY_A + KEY_B)  # 12 bytes per sector
    print(f"wrote 192 bytes → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make-hf-mf-key-bin.py <output.bin>")
    build(Path(sys.argv[1]))