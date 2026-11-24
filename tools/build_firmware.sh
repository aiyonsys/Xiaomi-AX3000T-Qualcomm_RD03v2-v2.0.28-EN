#!/usr/bin/env bash
# Assemble the localized firmware .bin:
#   1. mksquashfs rootfs_en -> ubi_rootfs.new  (xz, 256K blocks, no xattrs)
#   2. build_ubi.py build                     -> payload.new.ubi (headers cloned)
#   3. HDR1 header (756 B, from the original) with updated size fields,
#      no 272 B signature trailer (verified/unneeded by the restore path)
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT_ORIG_DIR="${1:-/home/tincan/Documents/deepseek-harness/default-workspace/xiaomi-ax3000t-rd03v2}"
ORIG="$ROOT_ORIG_DIR/miwifi_rd03v2_firmware_31bf9_2.0.28.bin"

mksquashfs rootfs_en ubi_rootfs.new -noappend -no-xattrs -comp xz \
    -Xbcj arm,armthumb -b 262144 -no-tailends -no-progress 2>&1 | tail -4

python3 tools/build_ubi.py build --original payload.ubi --kernel kernel \
    --rootfs ubi_rootfs.new --out payload.new.ubi

python3 - "$ORIG" <<'EOF'
import struct, sys, hashlib
orig_path = sys.argv[1]
d = bytearray(open(orig_path, "rb").read())
payload = open("payload.new.ubi", "rb").read()
assert d[:4] == b"HDR1", "original is not HDR1"
# field 0x04 (LE uint32): total = 756 + payload length
# field 0x2cc (LE uint32): payload length
hdr = bytes(d[:756])
hdr = bytearray(hdr)
struct.pack_into("<I", hdr, 4, 756 + len(payload))
old_payload_total = struct.unpack_from("<I", d, 4)[0]
struct.pack_into("<I", hdr, 0x2cc, len(payload))
out = bytes(hdr) + payload
name = "miwifi_rd03v2_firmware_localized-en_2.0.28.bin"
open(name, "wb").write(out)
h = hashlib.sha256()
h.update(open(name, "rb").read())
print(f"wrote {name}: {len(out)} B (header 756 + payload {len(payload)})")
print(f"sha256 {h.hexdigest()}")
print(f"old payload was {old_payload_total - 756} B; new is {len(payload)} B")
EOF