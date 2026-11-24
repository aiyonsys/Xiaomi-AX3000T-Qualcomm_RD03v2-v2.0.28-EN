#!/usr/bin/env python3
"""Build a raw UBI image for the RD03v2 stock payload by CLONING the original
image's PEB headers and replacing only volume data.

Why cloning instead of generating: the image's EC/VID crc fields are produced by
an unknown CRC variant (not zlib crc32 — verified against crc32/mpeg/bzip2/
castagnoli/xfer/adler32/fnv). But the header content depends only on
(vol_id, lnum), a small finite set that the original image already contains, so
cloning its 64+64 header bytes per PEB is exact and safe. The LEB count must not
grow beyond the original volume sizes (new data must fit: kernel 29 LEBs,
ubi_rootfs 149 LEBs); check after mksquashfs.

Usage:
  build_ubi.py roundtrip --original payload.ubi      # byte-identity proof
  build_ubi.py build --kernel kernel --rootfs rootfs --out payload.new.ubi
"""

import argparse
import sys

PEB_SIZE = 131072
VID_HDR_OFF = 2048
DATA_OFF = 4096
LEB_SIZE = PEB_SIZE - DATA_OFF
LAYOUT_VOL_ID = 0x7FFFEFFF
VTBL_RECORD = 172
VTBL_RECORDS = 128

sys.path.insert(0, "/home/tincan/Documents/deepseek-harness/default-workspace/"
                   "xiaomi-ax3000t-rd03v2/xiaomi-openwrt-install")
import ubiparse  # noqa: E402


def load_original(path):
    """Parse the original payload into templates + volume contents."""
    data = open(path, "rb").read()
    img = ubiparse.UbiImage(data, peb_size=PEB_SIZE)
    vols = {}
    for vid, v in img.volumes.items():
        if vid == LAYOUT_VOL_ID or not v.lebs:
            continue
        vols[v.name] = img.extract(vid)

    templates = {}      # (vol_id, lnum) -> (ec64, vid64, data_offset)
    data_lebs = {}      # (vol_id, lnum) -> data bytes (clipped to LEB_SIZE)
    for i in range(len(data) // PEB_SIZE):
        p = data[i * PEB_SIZE:(i + 1) * PEB_SIZE]
        if p[0:4] != b"UBI#":
            continue
        ec = p[0:64]
        vid = p[VID_HDR_OFF:VID_HDR_OFF + 64]
        vol_id = int.from_bytes(vid[8:12], "big")
        lnum = int.from_bytes(vid[12:16], "big")
        templates[(vol_id, lnum)] = (ec, vid)
        if (vol_id, lnum) not in ((LAYOUT_VOL_ID, 0), (LAYOUT_VOL_ID, 1)):
            data_lebs[(vol_id, lnum)] = p[DATA_OFF:]
    return data, vols, templates


def make_peb(ec, vid, data):
    buf = bytearray(b"\xff" * PEB_SIZE)
    buf[0:64] = ec
    buf[VID_HDR_OFF:VID_HDR_OFF + 64] = vid
    if len(data) > LEB_SIZE:
        raise ValueError(f"data {len(data)} exceeds LEB {LEB_SIZE}")
    buf[DATA_OFF:DATA_OFF + len(data)] = data
    return bytes(buf)


def split_lebs(raw, keep):
    data = raw + b"\xff" * (keep * LEB_SIZE - len(raw))
    if len(raw) > keep * LEB_SIZE:
        raise ValueError(f"volume needs {(len(raw)+LEB_SIZE-1)//LEB_SIZE} LEBs, "
                         f"budget is {keep} — compress harder or shrink")
    return [data[i * LEB_SIZE:(i + 1) * LEB_SIZE] for i in range(keep)]


def build_image(orig_data, vols, templates, kernel_keep, rootfs_keep):
    kernel = split_lebs(vols["kernel"], kernel_keep)
    rootfs = split_lebs(vols["ubi_rootfs"], rootfs_keep)
    out = bytearray()
    out += orig_data[0:PEB_SIZE]                       # layout LEB0 incl. vtbl
    out += orig_data[PEB_SIZE:2 * PEB_SIZE]            # layout LEB1 incl. vtbl
    for lnum, chunk in enumerate(kernel):
        ec, vid = templates[(0, lnum)]
        out += make_peb(ec, vid, chunk)
    for lnum, chunk in enumerate(rootfs):
        ec, vid = templates[(1, lnum)]
        out += make_peb(ec, vid, chunk)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["roundtrip", "build"])
    ap.add_argument("--original", default="payload.ubi")
    ap.add_argument("--kernel", default="kernel")
    ap.add_argument("--rootfs", default="ubi_rootfs.new")
    ap.add_argument("--kernel-lebs", type=int, default=29)
    ap.add_argument("--rootfs-lebs", type=int, default=149)
    ap.add_argument("--out", default="payload.new.ubi")
    args = ap.parse_args()

    orig_data, orig_vols, templates = load_original(args.original)

    if args.action == "roundtrip":
        built = build_image(orig_data, orig_vols, templates,
                            args.kernel_lebs, args.rootfs_lebs)
        print(f"original {len(orig_data)} B, rebuilt {len(built)} B")
        if built == orig_data:
            print("ROUND-TRIP: byte identical")
            return 0
        n = min(len(orig_data), len(built))
        dif = [i for i in range(n) if orig_data[i] != built[i]]
        print(f"ROUND-TRIP MISMATCH: {len(dif)} bytes; first "
              f"{[(i, hex(orig_data[i]), hex(built[i])) for i in dif[:6]]}")
        return 1

    kernel = open(args.kernel, "rb").read() if args.kernel != "SAME" \
        else orig_vols["kernel"]
    rootfs = open(args.rootfs, "rb").read() if args.rootfs != "SAME" \
        else orig_vols["ubi_rootfs"]
    vols = {"kernel": kernel, "ubi_rootfs": rootfs}
    built = build_image(orig_data, vols, templates,
                        args.kernel_lebs, args.rootfs_lebs)
    open(args.out, "wb").write(built)
    n_lebs = (len(rootfs) + LEB_SIZE - 1) // LEB_SIZE
    print(f"wrote {args.out}: {len(built)} B = {len(built)//PEB_SIZE} PEBs "
          f"(rootfs {len(rootfs)} B = {n_lebs} LEBs of "
          f"{args.rootfs_lebs} budget)")
    return 0


if __name__ == "__main__":
    sys.exit(main())