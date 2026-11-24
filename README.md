# Xiaomi AX3000T (RD03v2) — English-localized stock firmware 2.0.28

> ⚠️ **EXPERIMENTAL / TEST BUILD — USE AT YOUR OWN RISK**
>
> This is a **community-made, AI-translated modification** of Xiaomi's stock firmware.
> It is **not** produced, endorsed or supported by Xiaomi. Flashing custom firmware can
> **brick your router**. Everything in this repository is provided **AS IS**, without
> warranty of any kind. **You alone are responsible** for any damage, data loss or
> bricked device. If you are not prepared to recover a dead router, do not flash this.
>
> ⚠️ **ТЕСТОВА ВЕРСИЯ — НА СОБСТВЕН РИСК** (пълно описание на български в
> [README.bg.md](README.bg.md))

---

## What is this

An English-localized build of the official Xiaomi stock firmware
`miwifi_rd03v2_firmware_31bf9_2.0.28.bin` for the **Xiaomi AX3000T (RD03v2)** Wi-Fi 6
router (ROM `2.0.28`, version code `131100`).

The stock Chinese web UI was translated to English and the firmware was repacked into
a flashable image:

| | Original | Localized |
|---|---|---|
| File | [`firmware/miwifi_rd03v2_firmware_31bf9_2.0.28.bin`](firmware/miwifi_rd03v2_firmware_31bf9_2.0.28.bin) | [`firmware/miwifi_rd03v2_firmware_localized-en_2.0.28.bin`](firmware/miwifi_rd03v2_firmware_localized-en_2.0.28.bin) |
| Size | 23 593 988 B | 23 593 716 B |
| SHA-256 | `3138342e564c7d7482fde4a90e1778830180f0eac15e1de5f3ad269f9ba9940f` | `7bcb0593db190dbde952e0b7de70dbb1ca45dfa0e1d708f57788bc9993f226d5` |

Translation coverage: **2 900 of 3 100 unique UI strings (93.5 %)** across the LuCI
console templates and the www SPA. The remainder (65 files, mostly one long
legal/privacy text) is listed in [`strings/remaining.tsv`](strings/remaining.tsv).

The **kernel is byte-identical** to the original — only the read-only rootfs
filesystem content changed.

---

## How it was made

Fully reproducible pipeline (all scripts in [`tools/`](tools/)):

```
stock .bin ──carve──▶ UBI payload (180 PEBs) ──extract──▶ kernel (FIT) + ubi_rootfs (squashfs)
                                                              │
                                              unsquashfs ──▶ rootfs tree
                                                              │
                    extract 3 100 unique Chinese strings ──▶ 8 batches
                                                              │
                                    AI-translated in parallel batches (rules + glossary)
                                                              │
                              validate + merge ──▶ map.tsv (2 900 pairs, 0 violations)
                                                              │
                              apply ──▶ rootfs_en (full copy + string replacement)
                                                              │
        mksquashfs (xz, 256 K blocks, BCJ arm/armthumb) ──▶ 18.7 MB, fits 148/149 LEBs
                                                              │
        UBI repack (headers byte-cloned from the original) ──▶ payload (180 PEBs)
                                                              │
                              HDR1 header + payload ──▶ localized .bin (no signature)
```

Key technical findings (documented in detail in [`docs/IMAGE-LAYOUT.md`](docs/IMAGE-LAYOUT.md)):

- The stock image is `HDR1` header (756 B) + raw UBI (180 × 128 KB PEBs) + 272 B RSA
  signature trailer.
- The UBI EC/VID headers use a **non-standard CRC variant** (not zlib crc32; checked
  against crc32/mpeg-2, bzip2, CRC32C, xfer, adler32, FNV). Therefore the repack
  **clones the original headers byte-for-byte** per (volume, LEB) pair and replaces
  only the data — verified by a byte-identical round-trip rebuild of the original.
- The translated rootfs must fit in the original 149-LEB volume budget; xz with
  **BCJ arm,armthumb filters** reaches 18.7 MB (budget 18.9 MB). Linux's xz decoder
  has supported these BCJ filters since the initial import, so the stock 4.4.60
  kernel can decompress it.

### Verification performed on the final image

| Check | Result |
|---|---|
| `restore.py --dry-run` (carve + volume inspection) | ✅ valid and restorable |
| UBI round-trip rebuild of the original payload | ✅ byte-identical |
| Kernel volume vs original | ✅ byte-identical |
| Volume table (vtbl) vs original | ✅ byte-identical |
| File inventory: dirs / files / symlinks vs original rootfs | ✅ 275/2515/435, none missing, none extra |
| File permissions / ownership | ✅ 0 differences |
| All out-of-scope files (1807) | ✅ byte-identical |
| LuCI `<% %>` marker counts in all 109 templates | ✅ 0 differences |
| `{$placeholder}` tokens in all in-scope files | ✅ 0 differences |
| `node --check` on all 49 www JS bundles | ✅ 0 syntax errors |
| Residual Chinese in scope text files | 65 files / 1 825 glyphs (untranslated remainder) |

---

## Installation

### ⚠️ Read first

- This image **cannot** be installed through the stock web UI and **cannot** be used
  with TFTP recovery (see [What NOT to do](#what-you-must-not-do)).
- The only supported path is a **raw write of the payload into flash slot 0** from a
  router running OpenWrt **from RAM** (initramfs).
- You need: a PC with Linux (or WSL2), Python 3.8+, an Ethernet cable, and the
  [openwrt-xiaomi-ax3000t-rd03v2](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)
  installer project (its `restore.py` performs the flash; its RUNBOOK documents how to
  boot the router into the OpenWrt RAM system first).

### Steps

1. **Prepare the OpenWrt RAM system** on the router following the
   [installer project's RUNBOOK](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)
   (documented no-UART pivot; the router must report `rootfs_type = tmpfs`).
2. **Download** `miwifi_rd03v2_firmware_localized-en_2.0.28.bin` and verify:

   ```bash
   sha256sum miwifi_rd03v2_firmware_localized-en_2.0.28.bin
   # must print: 7bcb0593db190dbde952e0b7de70dbb1ca45dfa0e1d708f57788bc9993f226d5
   ```

3. **Flash from the RAM system** (replace `192.168.1.1` with the router's address):

   ```bash
   python3 restore.py miwifi_rd03v2_firmware_localized-en_2.0.28.bin \
       --device rd03v2 --host 192.168.1.1 --yes \
       --expected-image-sha256 7bcb0593db190dbde952e0b7de70dbb1ca45dfa0e1d708f57788bc9993f226d5
   ```

   `--expected-image-sha256` is **required**: this image is not on the project's
   published-hash list (it is modified), so you must accept its digest explicitly.

4. **Wait.** The router reboots into the localized stock firmware. Do **not** power it
   off during the write/reboot.

---

## What you MUST NOT do

- ❌ **Do NOT flash this image through the stock Xiaomi web UI** (upgrade page).
  It has no valid RSA signature — it will be rejected at best, and attempting
  workarounds can corrupt the router.
- ❌ **Do NOT use TFTP recovery with this image.** U-Boot's recovery path verifies the
  signature and will refuse it.
- ❌ **Do NOT interrupt power** while `restore.py` is writing or while the router
  reboots afterwards. A mid-write power loss can brick the device.
- ❌ **Do NOT flash it on any other device or hardware revision.** It is built for
  RD03v2 (`xiaomi.router.rd03v2`) only. Other AX3000T variants (RD03, international
  AX3000T) have different layouts.
- ❌ **Do NOT use it on a firmware version other than 2.0.28.** It was built and
  tested against exactly this image; mixing versions is untested.
- ❌ **Do NOT skip the RAM (initramfs) requirement.** Running the flash from an
  installed system erases the partition the running system lives on — the machine
  dies mid-write.
- ❌ **Do NOT trust any checksum other than the ones in this README /
  `firmware/SHA256SUMS`.** Always verify after download.
- ❌ **Do NOT use a `--host`/setup you do not understand.** Read the installer
  project's documentation first.

## Rollback

To return to a fully stock router, download the official image from Xiaomi's CDN and
flash it the same way (`restore.py`), **or** use U-Boot TFTP recovery — the official
image has a valid signature and is accepted by every path, including recovery. Keep a
copy of the original:
[`firmware/miwifi_rd03v2_firmware_31bf9_2.0.28.bin`](firmware/miwifi_rd03v2_firmware_31bf9_2.0.28.bin)
(SHA-256 `3138342e…9940f` — verify before use).

---

## Repository contents

```
├── firmware/
│   ├── miwifi_rd03v2_firmware_31bf9_2.0.28.bin          original stock image (backup)
│   ├── miwifi_rd03v2_firmware_localized-en_2.0.28.bin   localized image (TEST)
│   └── SHA256SUMS
├── tools/                     full build & verification pipeline
│   ├── extract_strings.py     extract unique Chinese UI strings (scope B)
│   ├── merge_map.py           validate + merge translations (strict checks)
│   ├── apply_translation.py   build rootfs_en (preserves dirs/perms/symlinks)
│   ├── build_ubi.py           UBI repacker w/ header cloning + round-trip proof
│   ├── build_firmware.sh      mksquashfs + UBI + HDR1 assembly
│   ├── verify_build.sh        end-to-end verification battery
│   └── fitdump.py             FIT/FDT parser (kernel inspection)
├── strings/
│   ├── RULES.md               translator contract (hard constraints)
│   ├── GLOSSARY.md            EN terminology used
│   ├── unique.tsv             3 100 unique source strings
│   ├── map.tsv                2 900 validated translations (zh → en)
│   └── remaining.tsv          the 200 untranslated strings
└── docs/
    └── IMAGE-LAYOUT.md        flash/UBI/squashfs format deep-dive
```

To rebuild the image yourself: unpack the original (see `tools/build_ubi.py --help`
and `docs/IMAGE-LAYOUT.md`), apply `strings/map.tsv` with `tools/apply_translation.py`,
then `tools/build_firmware.sh`. Every step is offline and verifiable.

## Known limitations

- ~6.5 % of strings remain Chinese (mostly the user-license/privacy long text and a
  few mixed-language fragments) — see `strings/remaining.tsv`.
- Translations were produced and cross-checked by multiple AI agents with automated
  validation; some phrasing may be imperfect. The legal texts are translations of
  Xiaomi's Chinese originals and are provided for convenience only — **the Chinese
  original is the only legally relevant text**.
- Deviations from the original binary that are known and benign: 14 hardlinked files
  are stored as content-identical duplicates (data deduplicated by squashfs); one UNC
  path hint renders `\\ip` instead of `\ip`; some `\n` escapes inside HTML text nodes
  were dropped (invisible after HTML whitespace collapsing).

## Credits & licenses

- Flashing/restore tooling and the UBI parser: the excellent
  [ADCDS/openwrt-xiaomi-ax3000t-rd03v2](https://github.com/ADCDS/openwrt-xiaomi-ax3000t-rd03v2)
  project (restore.py, ubiparse.py) — all rights remain with its authors.
- Translation pipeline, repack tooling and this repository: MIT (see
  [LICENSE](LICENSE)).
- `miwifi_rd03v2_firmware_31bf9_2.0.28.bin` and the localized derivative contain
  **Xiaomi's copyrighted firmware**. They are hosted here solely as a backup and for
  educational/interoperability purposes, for owners of this hardware. All firmware
  rights belong to Xiaomi. If you are Xiaomi and object, open an issue and it will be
  removed.

---

*Built and verified on 2026-11-24. No unit was flashed during preparation — all
verification was structural (offline). Flashing is performed entirely at your own
risk.*
