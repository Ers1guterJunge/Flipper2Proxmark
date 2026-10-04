#!/usr/bin/env python3
"""
flipper-nfc-to-bin.py — convert Flipper Zero `.nfc` dumps into a raw 1024-byte
binary suitable for `hf mf restore` / `hf mf wrbl --force` on a Mifare Classic
1K CUID (magic) card.

Usage:
    flipper-nfc-to-bin.py <input.nfc> [<output.bin>]

If <output.bin> is omitted, the script writes next to the input with a `.bin`
suffix. Block 0's BCC is recomputed from the UID bytes; if the source value
disagrees, a one-line warning is printed to stderr and the corrected BCC is
written.

This script DOES NOT write to the card. After conversion, write the binary to
your magic CUID card with one of:

    # Gen 1a (direct-write) magic cards
    proxmark3 -p /dev/ttyACM0 -c "hf mf wrbl --1k --force --blk 0 -k A0A1A2A3A4A5 -f Michael.bin"

    # Gen 2 / Gen 1b (UID-changeable via backdoor auth)
    proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k --uid --gen2 -f Michael.bin"
    # or, for Gen 1a specifically:
    proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k -f Michael.bin"

Verify after writing:
    proxmark3 -p /dev/ttyACM0 -c "hf mf info"
"""

import argparse
import re
import sys
from pathlib import Path


BLOCK_HEX_RE = re.compile(r"^Block\s+(\d+):\s*(.*)$")


def parse_nfc(text: str) -> bytes:
    """Parse a Flipper Zero `.nfc` Mifare Classic dump into 64 blocks (1024 bytes).

    Raises SystemExit on malformed input or wrong card type.
    """
    lines = text.splitlines()

    # Sanity-check header
    head = "\n".join(lines[:15])
    if "Filetype: Flipper NFC device" not in head:
        sys.exit("error: input is not a Flipper Zero `.nfc` file")
    if "Device type: Mifare Classic" not in head:
        sys.exit("error: this script handles Mifare Classic only (not Ultralight / FeliCa / etc.)")
    if "Mifare Classic type: 1K" not in head:
        sys.exit("error: only Mifare Classic 1K is supported (need exactly 64 blocks)")

    blocks: dict[int, bytes] = {}

    for raw in lines:
        m = BLOCK_HEX_RE.match(raw.strip())
        if not m:
            continue
        block_no = int(m.group(1))
        hex_bytes = m.group(2).split()
        if len(hex_bytes) != 16:
            sys.exit(f"error: block {block_no} has {len(hex_bytes)} bytes, expected 16")
        try:
            blocks[block_no] = bytes(int(b, 16) for b in hex_bytes)
        except ValueError as exc:
            sys.exit(f"error: block {block_no} contains non-hex byte: {exc}")

    if sorted(blocks.keys()) != list(range(64)):
        sys.exit(f"error: expected 64 blocks (0-63), got {len(blocks)}")

    # Concatenate in block order
    return b"".join(blocks[i] for i in range(64))


def fix_bcc(block0: bytearray) -> bool:
    """Recompute block 0 byte 4 (BCC) from UID bytes 0-3.

    Mifare Classic block 0 layout:
        byte 0-3:  UID (4 bytes)
        byte 4:    BCC = UID[0] ^ UID[1] ^ UID[2] ^ UID[3]
        byte 5-6:  ATQA
        byte 7:    manufacturer byte
        byte 8:    SAK
        bytes 9-15: manufacturer data

    Returns True if the byte was patched, False if it was already correct.
    Prints a one-line warning to stderr on patch.
    """
    uid = block0[:4]
    expected = uid[0] ^ uid[1] ^ uid[2] ^ uid[3]
    actual = block0[4]
    if actual == expected:
        return False
    block0[4] = expected
    print(
        f"warning: block 0 BCC was 0x{actual:02X}, "
        f"corrected to 0x{expected:02X} (UID XOR)",
        file=sys.stderr,
    )
    return True


def main() -> int:
    p = argparse.ArgumentParser(
        description="Convert Flipper Zero `.nfc` Mifare Classic dump → raw 1024-byte binary."
    )
    p.add_argument("input", type=Path, help="path to input `.nfc` file")
    p.add_argument("output", type=Path, nargs="?", help="path to output `.bin` (default: <input>.bin)")
    args = p.parse_args()

    src: Path = args.input
    if not src.is_file():
        sys.exit(f"error: input not found: {src}")

    dst: Path = args.output or src.with_suffix(".bin")

    try:
        text = src.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sys.exit(f"error: {src} is not a text file (looks like binary, not a `.nfc`)")

    raw_bytes = parse_nfc(text)

    # Make the binary mutable, recompute BCC, write
    mutable = bytearray(raw_bytes)
    fix_bcc(mutable)

    dst.write_bytes(bytes(mutable))
    print(f"wrote {len(mutable)} bytes → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())