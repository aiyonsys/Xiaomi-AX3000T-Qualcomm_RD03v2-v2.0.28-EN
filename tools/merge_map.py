#!/usr/bin/env python3
"""Merge + validate translator batch outputs into strings/map.tsv.

Input rows in the batch files are expected to carry the zh column EXACTLY as it
appears in strings/unique.tsv (i.e. JSON-escaped). The same for en when it
contains quotes/backslashes. This script normalizes both sides, validates the
translation, and writes strings/map.tsv as real text (TSV, no JSON escaping) so
the applier can do plain byte replacement.

Checks per row (zh, en):
  - zh resolves to a key of strings/unique.tsv
  - en has no CJK
  - en has no ASCII " or backslash unless zh already had that char
  - placeholder tokens (\$N, {...}, %s) multiset unchanged
  - <%: ... %> markers preserved when present in zh
"""

import glob
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STR = os.path.join(BASE, "strings")

CJK = re.compile(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
TOKEN = re.compile(r"\{\$?[\w\.]*\}|\$\d+|%[-+ #0]*\d*(?:\.\d+)?[sdifouxXeEgGc]")


def unescape_force(s):
    """Residual escape cleanup for translators that hand-wrote \" or \\. """
    s = s.replace('\\\\', '\x00').replace('\\"', '"').replace('\x00', '\\')
    return s


def unwrap(s):
    """Raw file text -> real string (JSON) with escape cleanup fallback."""
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        try:
            v = json.loads(s)
            if isinstance(v, str):
                return v
        except json.JSONDecodeError:
            return unescape_force(s[1:-1])
    return unescape_force(s)


def load_unique():
    out = {}
    for ln in open(os.path.join(STR, "unique.tsv"), encoding="utf-8"):
        zh_raw, cnt = ln.rstrip("\n").split("\t")
        out[unwrap(zh_raw)] = int(cnt)
    return out


def tokens(s):
    return Counter(TOKEN.findall(s))


def problems(zh, en):
    p = []
    if CJK.search(en):
        p.append("CJK in en")
    # ASCII quotes/backslashes may ONLY pass through from zh (full-width “ ” in
    # zh are NOT ASCII quotes: converting them to " breaks JS string literals).
    if '"' in en and '"' not in zh:
        p.append('ASCII " introduced')
    if "\\" in en and "\\" not in zh:
        p.append("backslash introduced")
    if "\n" in en and "\n" not in zh:
        p.append("newline in en")
    if tokens(zh) != tokens(en):
        p.append(f"token mismatch zh={dict(tokens(zh))} en={dict(tokens(en))}")
    # marker counts must match exactly (covers markers wrapped around HTML too)
    if zh.count("<%") != en.count("<%") or zh.count("%>") != en.count("%>"):
        p.append("luci marker count mismatch")
    return p


def main():
    unique = load_unique()
    rows = {}
    bad = []
    srcs = (glob.glob(os.path.join(STR, "batches", "*.en.tsv")) +
            glob.glob(os.path.join(STR, "rbatches", "*.en.tsv")))
    for f in sorted(srcs):
        for lineno, ln in enumerate(open(f, encoding="utf-8"), 1):
            if not ln.strip():
                continue
            parts = ln.rstrip("\n").split("\t")
            if len(parts) != 2:
                bad.append((os.path.basename(f), lineno, ln[:60], "",
                            ["not 2 columns"]))
                continue
            zh = unwrap(parts[0])
            en = unwrap(parts[1])
            if zh not in unique:
                bad.append((os.path.basename(f), lineno, zh, en,
                            ["zh not in unique.tsv"]))
                continue
            if zh in rows:
                bad.append((os.path.basename(f), lineno, zh, en,
                            ["duplicate zh"]))
                continue
            probs = problems(zh, en)
            if probs:
                bad.append((os.path.basename(f), lineno, zh, en, probs))
                continue
            rows[zh] = en

    with open(os.path.join(STR, "map.tsv"), "w", encoding="utf-8") as fh:
        for zh in sorted(rows, key=lambda z: unique[z]):
            fh.write(json.dumps(zh, ensure_ascii=False) + "\t" +
                     json.dumps(rows[zh], ensure_ascii=False) + "\n")

    print(f"merged rows: {len(rows)} / {len(unique)} unique")
    if bad:
        print(f"VIOLATIONS: {len(bad)}")
        for src, ln, zh, en, probs in bad[:40]:
            print(f"  {src}:{ln} {probs} zh={zh!r} en={en!r}")
        return 1
    print("all rows pass validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())