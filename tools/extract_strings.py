#!/usr/bin/env python3
"""Extract Chinese UI strings of scope B (www + luci view templates) into TSV files.

Units:
  js_string  - inner content of a JS string literal ('...', "...", `...`) containing CJK
  js_text    - unquoted CJK run (identifier) not covered by a literal
  lua_i18n   - inner text of a LuCI translate marker <%: ... %>
  html_text  - CJK run in plain HTML (text or attribute value)

Output (UTF-8, JSON-escaped values to keep one record per line):
  strings/units.tsv    id  kind  path  line  zh
  strings/unique.tsv   zh  count
"""

import json
import os
import re
import sys
from collections import Counter

CJK_IDEO = re.compile(r"[\u4e00-\u9fff]")
CJK_RUN = re.compile(
    r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef\u2000-\u200f\u2026\u2018\u2019\u201c\u201d\u2014\u00b7]+"
)
SKIP_EXT = {
    ".png", ".gif", ".jpg", ".jpeg", ".woff", ".woff2", ".eot",
    ".ttf", ".svg", ".ico", ".bin", ".gz", ".xz", ".tar",
}
LAYERS = ["rootfs/www", "rootfs/usr/lib/lua/luci/view"]

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # stock-en/
OUT_DIR = os.path.join(BASE, "strings")


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan_js_literals(text):
    """String-literal spans in JS source; crude but sufficient for bundles."""
    literals = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    break
                j += 1
            literals.append((i, min(j + 1, n)))
            i = literals[-1][1]
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i)
            i = n if j < 0 else j + 2
        else:
            i += 1
    return literals


def js_units(text):
    units = []
    literals = scan_js_literals(text)
    lit_spans = []
    for (s, e) in literals:
        raw = text[s:e]
        if len(raw) < 3:  # '' or "
            lit_spans.append((s, e))
            continue
        inner = raw[1:-1]
        if CJK_IDEO.search(inner):
            units.append(("js_string", s, inner))
        lit_spans.append((s, e))

    def covered(s, e):
        for (a, b) in lit_spans:
            if a <= s < b:
                return True
        return False

    for m in CJK_RUN.finditer(text):
        s, e = m.span()
        if covered(s, e):
            continue
        if len(m.group(0)) >= 2 and CJK_IDEO.search(m.group(0)):
            units.append(("js_text", s, m.group(0)))
    units.sort(key=lambda u: u[1])
    return units


def html_units(text):
    """Split out <script> blocks; inside them use the JS scanner."""
    units = []
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I):
        for (kind, s, zh) in js_units(m.group(1)):
            units.append((kind, m.start(1) + s, zh))
    masked = re.sub(r"<script\b[^>]*>.*?</script\s*>", "\x00" * 0, text, flags=re.S | re.I)
    # Build a mask: replace script blocks with equal-length placeholder so offsets survive.
    masked_chars = list(text)
    for m in re.finditer(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I):
        for i in range(m.start(), m.end()):
            masked_chars[i] = "\n" if masked_chars[i] == "\n" else "\x00"
    masked = "".join(masked_chars)

    luci_spans = []
    for m in re.finditer(r"<%:(.*?)%>", masked, re.S):
        inner = m.group(1)
        if CJK_IDEO.search(inner):
            units.append(("lua_i18n", m.start(1), inner))
        luci_spans.append((m.start(), m.end()))

    def covered(s, e):
        for (a, b) in luci_spans:
            if a <= s < b:
                return True
        return False

    for m in CJK_RUN.finditer(masked):
        s, e = m.span()
        if covered(s, e):
            continue
        if len(m.group(0)) >= 2 and CJK_IDEO.search(m.group(0)):
            units.append(("html_text", s, m.group(0)))
    units.sort(key=lambda u: u[1])
    return units


def file_units(path, text):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".js", ".mjs"):
        return js_units(text)
    if ext in (".htm", ".html", ".json", ".css"):
        return html_units(text)
    if ext in (".lua", ".sh", ".conf", ".txt"):
        return js_units(text)
    return html_units(text)


def is_text_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in SKIP_EXT:
        return False
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    if b"\x00" in head:
        return False
    return True


def main():
    units = []
    seen_files = 0
    for layer in LAYERS:
        for root, _dirs, files in os.walk(os.path.join(BASE, layer)):
            for f in sorted(files):
                p = os.path.join(root, f)
                if os.path.islink(p) or not is_text_file(p):
                    continue
                try:
                    text = open(p, "r", encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                rel = os.path.relpath(p, BASE)
                got = file_units(rel, text)
                if not got:
                    continue
                seen_files += 1
                for (kind, pos, zh) in got:
                    if zh.strip() == "":
                        continue
                    units.append({
                        "kind": kind,
                        "path": rel,
                        "line": line_of(text, pos),
                        "zh": zh,
                    })

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "units.tsv"), "w", encoding="utf-8") as fh:
        for i, u in enumerate(units):
            fh.write("\t".join([
                str(i), u["kind"], u["path"], str(u["line"]),
                json.dumps(u["zh"], ensure_ascii=False),
            ]) + "\n")

    counts = Counter(u["zh"] for u in units)
    with open(os.path.join(OUT_DIR, "unique.tsv"), "w", encoding="utf-8") as fh:
        for zh, cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            fh.write(json.dumps(zh, ensure_ascii=False) + "\t" + str(cnt) + "\n")

    by_kind = Counter(u["kind"] for u in units)
    by_layer = Counter(
        "www" if u["path"].startswith("rootfs/www") else "luci-view" for u in units
    )
    print(f"files with units: {seen_files}")
    print(f"total units: {len(units)}  unique: {len(counts)}")
    print("by kind:", dict(by_kind))
    print("by layer:", dict(by_layer))


if __name__ == "__main__":
    sys.exit(main())