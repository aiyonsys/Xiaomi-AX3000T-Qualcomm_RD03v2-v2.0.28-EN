#!/usr/bin/env python3
"""Apply strings/map.tsv to scope-B files, writing rootfs_en/ (mirror tree).

v2 (fixed after audit):
  - copytree() the WHOLE source tree first: empty directories (mount points
    like /proc /sys /dev /tmp /overlay are critical at boot), permissions and
    symlinks are preserved exactly.
  - only in-scope text files are re-written in place; open(dst, "w") keeps the
    existing inode, so mode bits survive.
  - the residual-CJK report counts TEXT files only (binaries contain CJK bytes
    in image data and are not translatable).
"""

import json
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "rootfs")
DST = os.path.join(BASE, "rootfs_en")
STR = os.path.join(BASE, "strings")

LAYERS = ["www", "usr/lib/lua/luci/view"]
SKIP_EXT = {".png", ".gif", ".jpg", ".jpeg", ".woff", ".woff2", ".eot",
            ".ttf", ".svg", ".ico", ".bin", ".gz", ".xz", ".tar"}
CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")


def in_scope(rel):
    return any(rel.startswith(layer + "/") for layer in LAYERS)


def is_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in SKIP_EXT:
        return False
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    return b"\x00" not in head


def load_map():
    pairs = []
    for ln in open(os.path.join(STR, "map.tsv"), encoding="utf-8"):
        zh_j, en_j = ln.rstrip("\n").split("\t")
        pairs.append((json.loads(zh_j), json.loads(en_j)))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def main():
    pairs = load_map()
    if os.path.exists(DST):
        shutil.rmtree(DST)
    # Full-fidelity copy: empty dirs, permissions, symlinks, everything.
    shutil.copytree(SRC, DST, symlinks=True)

    changed = replaced = 0
    for root, _dirs, files in os.walk(SRC):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, SRC)
            if os.path.islink(src) or not in_scope(rel) or not is_text(src):
                continue
            try:
                text = open(src, "r", encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            orig = text
            n = 0
            for zh, en in pairs:
                if zh in text:
                    n += text.count(zh)
                    text = text.replace(zh, en)
            if text != orig:
                dst = os.path.join(DST, rel)
                # open for write truncates in place -> mode/owner preserved
                with open(dst, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
                changed += 1
                replaced += n

    print(f"scope files translated: {changed}, total replacements: {replaced}")

    # verification: no CJK left in translated scope TEXT files
    left = []
    for root, _dirs, files in os.walk(DST):
        for f in files:
            p = os.path.join(root, f)
            if os.path.islink(p) or not is_text(p):
                continue
            rel = os.path.relpath(p, DST)
            if not in_scope(rel):
                continue
            txt = open(p, "r", encoding="utf-8", errors="replace").read()
            if CJK.search(txt):
                left.append((rel, len(CJK.findall(txt))))
    if left:
        print(f"RESIDUAL CJK in {len(left)} scope text files:")
        for rel, n in sorted(left, key=lambda x: -x[1])[:25]:
            print(f"  {rel}: {n} glyphs")
        return 1
    print("scope-B text files fully translated (no CJK left)")
    return 0


if __name__ == "__main__":
    sys.exit(main())