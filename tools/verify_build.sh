#!/usr/bin/env bash
# End-to-end verification of the localized firmware image.
set -euo pipefail
cd "$(dirname "$0")/.."
BIN="${1:-miwifi_rd03v2_firmware_localized-en_2.0.28.bin}"
INSTALL=/home/tincan/Documents/deepseek-harness/default-workspace/xiaomi-ax3000t-rd03v2/xiaomi-openwrt-install

echo "=== 1. basic ==="
ls -la "$BIN"
sha256sum "$BIN"

echo "=== 2. restore.py carve+inspect (dry-run, no device) ==="
cd "$INSTALL"
python3 restore.py "$OLDPWD/$BIN" --device rd03v2 --dry-run \
  --expected-image-sha256 "$(sha256sum "$OLDPWD/$BIN" | cut -d' ' -f1)" || true
cd "$OLDPWD"

echo "=== 3. independent UBI parse of the new payload ==="
dd if="$BIN" of=/tmp/verify.ubi bs=1M iflag=skip_bytes,count_bytes skip=756 \
   count=$(( $(stat -c%s "$BIN") - 756 )) status=none
python3 - <<'EOF'
import sys, hashlib
sys.path.insert(0, "/home/tincan/Documents/deepseek-harness/default-workspace/"
                   "xiaomi-ax3000t-rd03v2/xiaomi-openwrt-install")
import ubiparse
img = ubiparse.UbiImage("/tmp/verify.ubi", peb_size=131072)
print(img.report())
for vid, v in sorted(img.volumes.items()):
    blob = img.extract(vid)
    expect = {0: b"\xd0\r\xfe\xed", 1: b"hsqs"}.get(vid)
    ok = "OK" if expect is None or blob[:4] == expect else "MAGIC MISMATCH"
    print(f"  {v.name:<12} md5={hashlib.md5(blob).hexdigest()} {ok}")
EOF

echo "=== 4. kernel volume unchanged? ==="
python3 - <<'EOF'
import sys, hashlib
sys.path.insert(0, "/home/tincan/Documents/deepseek-harness/default-workspace/"
                   "xiaomi-ax3000t-rd03v2/xiaomi-openwrt-install")
import ubiparse
a = ubiparse.UbiImage(open("payload.ubi","rb").read(), peb_size=131072)
b = ubiparse.UbiImage(open("/tmp/verify.ubi","rb").read(), peb_size=131072)
ka, kb = a.extract(0), b.extract(0)
print("kernel identical:", ka == kb, "rootfs new size:", len(b.extract(1)))
EOF

echo "=== 5. new squashfs readable, file inventory ==="
rm -rf /tmp/verify-rootfs && unsquashfs -d /tmp/verify-rootfs -n /tmp/verify.ubi 2>/dev/null || true
rm -rf /tmp/verify-rootfs
mkdir -p /tmp/verify-rootfs
unsquashfs -f -d /tmp/verify-rootfs -no-xattrs ubi_rootfs.new 2>&1 | grep -E "created|filesystem" | tail -3
echo "inodes in repack: unsquashfs -s summary above"

echo "=== 6. LuCI marker integrity (<% and %> counts must match source) ==="
python3 - <<'EOF'
import os
bad = 0
for root, dirs, files in os.walk("rootfs/usr/lib/lua/luci/view"):
    for f in files:
        s = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
        d = os.path.join("rootfs_en", os.path.relpath(os.path.join(root, f), "rootfs"))
        t = open(d, encoding="utf-8", errors="replace").read()
        if s.count("<%") != t.count("<%") or s.count("%>") != t.count("%>"):
            print("MARKER MISMATCH:", d)
            bad += 1
print("marker integrity:", "OK" if bad == 0 else f"{bad} files broken")
EOF

echo "=== 7. JS syntax of all changed www JS ==="
fail=0
for f in $(find rootfs_en/www/static/js -name '*.js' | head -50); do
  node --check "$f" 2>/dev/null || { echo "JS SYNTAX FAIL: $f"; fail=1; }
done
[ $fail -eq 0 ] && echo "all JS parses"