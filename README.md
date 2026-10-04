# Flipper2Proxmark

Convert Flipper Zero `.nfc` dumps of **Mifare Classic 1K** cards into the raw
binary format that Proxmark3 (or a Gen 1a / Gen 2 magic CUID card) can read
back.

```
.nfc  ──►  flipper-nfc-to-bin.py  ──►  .bin  ──►  Proxmark3 / magic CUID card
```

This repo is for working with cards you own: backing up access cards,
restoring them to a new physical card, NFC forensics learning, CTF prep.

---

## What's in this repo

| File | Purpose |
|------|---------|
| `flipper-nfc-to-bin.py` | Convert a `.nfc` text dump from the Flipper Zero into a 1024-byte raw binary suitable for `hf mf restore` or writing to a magic CUID card. Auto-corrects the BCC byte in block 0. |
| `make-hf-mf-key-bin.py` | Generate a PM3-format `hf-mf-<UID>-key.bin` keys file from the NXP factory transport keys, for use with `hf mf restore`. |
| `.gitignore` | Excludes real card dumps (`.bin`, `.nfc`, `.json`, `hf-mf-*-key.bin`, log files). Never commit your captures. |

Both scripts are stdlib-only — no `pip install` required.

---

## Quick start

### 1. Capture a card with the Flipper Zero

On the Flipper: **NFC → Saved → Read** for the card you want to back up.
The Flipper saves it as a `.nfc` text file on its SD card. Copy it to your
machine (e.g. via qFlipper or by mounting the SD card).

### 2. Convert `.nfc` to raw `.bin`

```bash
./flipper-nfc-to-bin.py capture.nfc capture.bin
# or just:
./flipper-nfc-to-bin.py capture.nfc
# → writes capture.bin next to capture.nfc
```

The script reads block 0 of the source, recomputes the BCC
(`BCC = UID[0] ⊕ UID[1] ⊕ UID[2] ⊕ UID[3]`), and warns on stderr if the
Flipper-captured value disagrees. Some Flipper firmware versions write the
last UID byte into the BCC slot — the fix is automatic.

If your `.nfc` is malformed, not a Mifare Classic, or not 1K (not exactly
64 blocks), the script refuses to convert.

### 3a. Restore to a fresh card with Proxmark3

```bash
# 1K Gen 1a magic card (most common CUID cards; block 0 directly writable)
proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k -f capture.bin"

# 1K Gen 2 / UID-changeable magic card (needs backdoor auth for block 0)
proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k --gen2 -f capture.bin"
```

If `hf mf restore` complains it can't find `hf-mf-<UID>-key.bin`,
generate one:

```bash
./make-hf-mf-key-bin.py hf-mf-6DF6F103-key.bin   # use the *target* card's UID
proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k -f capture.bin -k hf-mf-6DF6F103-key.bin"
```

### 3b. Write to a magic CUID card when `hf mf restore` fails

Some clone chips (Fudan FM11RF08S, certain "Gen 1a" labeled CUID cards) only
honor block 0 via the magic backdoor command. If a normal restore silently
keeps the factory UID, drop down to the magic primitives:

```bash
# Set UID + ATQA + SAK via Gen 1a backdoor (UID-only, doesn't touch other blocks)
proxmark3 -p /dev/ttyACM0 -c "hf mf csetuid -u AABBCCDD --atqa 0400 --sak 08"

# Write block 0 bytes verbatim via Gen 1a backdoor
proxmark3 -p /dev/ttyACM0 -c "hf mf csetblk -b 0 -d AABBCCDDxxxxxxx..."

# Then write the rest of the dump block-by-block with normal auth
proxmark3 -p /dev/ttyACM0 -c "hf mf restore --1k -f capture.bin"
```

### 4. Verify

```bash
proxmark3 -p /dev/ttyACM0 -c "hf mf info"
# → UID, ATQA, SAK should match the source card

proxmark3 -p /dev/ttyACM0 -c "hf mf rdbl --blk 0 -k A0A1A2A3A4A5"
# → block 0 bytes (manufacturer data may vary by chip)
```

---

## Background: Mifare Classic block 0 layout

Block 0 of a Mifare Classic card has a fixed layout:

| Byte | Field |
|------|-------|
| 0–3  | UID (4 bytes for 1K) |
| 4    | BCC = UID[0] ⊕ UID[1] ⊕ UID[2] ⊕ UID[3] |
| 5–6  | ATQA (2 bytes) |
| 7    | Manufacturer byte |
| 8    | SAK |
| 9–15 | Manufacturer data |

A wrong BCC means most readers will reject the card outright, even if every
other byte is correct. This is why `flipper-nfc-to-bin.py` checks it.

A real Classic 1K has bytes 0–7 locked from the factory. Magic CUID cards
("Gen 1a" / "Gen 2") have one of two unlock mechanisms:

- **Gen 1a**: block 0 is writable with the standard write command after
  authenticating with `A0A1A2A3A4A5` — but only on certain chips. Fudan-based
  clones silently drop block 0 writes and need `hf mf csetuid`/`csetblk`.
- **Gen 2 / UID-changeable**: block 0 can only be written via a special
  "backdoor" authentication sequence. PM3 exposes this as `--gen2` flag on
  `hf mf restore`.

---

## What this repo isn't

- **Not** a card cloner for cards you don't own. Cloning access-control cards,
  transit passes, hotel keys, or payment cards without authorization is illegal
  in most jurisdictions and unethical everywhere.
- **Not** a fork of the Proxmark3 client. PM3 is the consumer of these
  scripts' output, but isn't redistributed here.
- **Not** a Flipper firmware alternative. The `.nfc` files come from the
  Flipper; this repo only post-processes them.

## Why the `.gitignore` is so aggressive

UIDs are unique identifiers. A committed dump reveals:
- the card serial number (often printed or tied to an account),
- the access patterns stored on it (keys, balances, identifiers),
- which facility or service the card belongs to.

Treat your captures like passwords: keep them on your machine, never in
git history.

---

## Requirements

- Python 3 (no extra packages — stdlib only)
- Proxmark3 with `proxmark3`/`pm3` client and a connected reader
- A magic CUID card (Gen 1a or Gen 2) if you intend to write to a fresh card