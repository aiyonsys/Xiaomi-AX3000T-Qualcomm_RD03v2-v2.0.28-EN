# RD03v2 stock firmware image layout (2.0.28)

Verified byte-level against `miwifi_rd03v2_firmware_31bf9_2.0.28.bin`
(SHA-256 `3138342e564c7d7482fde4a90e1778830180f0eac15e1de5f3ad269f9ba9940f`).

## Top-level container

```
offset        size         content
0x000000      756 B        HDR1 header (magic "HDR1")
0x0002F4      23 592 960 B raw UBI payload (180 PEBs × 131 072 B)
0x2F4+23 592 960   272 B   RSA-2048 signature trailer
```

- `HDR1 @0x04` (LE u32) = `756 + payload` size (excludes the signature trailer).
- `HDR1 @0x2CC` (LE u32) = payload size.
- `HDR1` also embeds a UCI config text block (ROM/channel/HARDWARE `RD03v2`,
  UBOOT `1.0.2`, LINUX `4.4.16` …) and the volume name `root.ubi`.
- The **signature is checked only by U-Boot's TFTP recovery path**. There is no
  secure boot on the kernel; a payload written straight into flash slot 0 needs no
  valid signature. The localized image therefore ships **without** the trailer.

## UBI payload (180 PEBs)

```
PEB 0..1     layout volume (volume table, 2 records: kernel=29, ubi_rootfs=149)
PEB 2..30    volume "kernel"     29 LEBs — FIT image (d00dfeed), Linux 4.4.60
PEB 31..179  volume "ubi_rootfs" 149 LEBs — squashfs 4.0, xz, 256 KB blocks
```

Per-PEB geometry (verified):

```
0x0000  EC header  (64 B, magic "UBI#"): ver=1, ec=0, vid_hdr_off=2048,
        data_off=4096, image_seq=546134002, CRC @60
0x0800  VID header (64 B, magic "UBI!"): vol_type@5, copy@6, compat@7
        (5=layout, 0=data), vol_id@8 (BE u32), lnum@12, CRC @60
0x1000  data (126 976 B usable), tail padded with 0xFF
```

Non-standard details that make blind regeneration impossible:

- The header CRC fields are **not zlib crc32** (checked: crc32/mpeg-2, bzip2,
  CRC32C, xfer, adler32, FNV — none match). The exact variant is unknown.
- All `sqnum`, `data_size`, `used_ebs`, `data_crc` VID fields are **zero** in this
  factory image (freshly built, never mounted).

Therefore the repacker (`tools/build_ubi.py`) **clones** the 64+64 header bytes per
(vol_id, lnum) pair from the original image and replaces only the data region.
`build_ubi.py roundtrip` rebuilds the untouched original payload byte-for-byte —
this is the proof the cloning is exact. Consequence: the translated rootfs must fit
the original volume sizes (kernel 29 LEBs — untouched; ubi_rootfs ≤ 149 LEBs).

## Rootfs squashfs

```
Squashfs 4.0, xz compressed, block size 262144, 18 739 360 B (original)
3213 inodes, 110 fragments, 14 hardlinks, xattrs not stored
```

The translated rebuild uses the same parameters plus **BCJ arm,armthumb** filters
(supported by Linux xz since the initial import — safe for the 4.4.60 kernel),
reaching 18 714 624 B = 148/149 LEBs. Inventory is preserved exactly:
275 directories, 2515 files, 435 symlinks, identical modes.

## Flash partition context (stock layout, from MIBIB)

```
stock  rootfs   0x0A80000..0x2880000  (30 MB)  ← slot 0  = where the payload is written
stock  rootfs_1 0x2880000..0x4680000  (30 MB)  ← slot 1
stock  overlay  0x4680000..0x8000000  (57 MB)
OpenWrt ubi_kernel 0x0A80000..0x2E80000 (36 MB)  ← starts at stock slot 0
OpenWrt rootfs      0x2E80000..0x8000000 (81 MB)
```

`restore.py` (from the openwrt-xiaomi-ax3000t-rd03v2 project) writes the payload at
the start of `ubi_kernel` (= stock slot 0), erases everything above stock's slot 0,
and points `flag_last_success` at slot 0. The stock bootloader then attaches the
written UBI and boots kernel + ubi_rootfs as if factory-flashed.
