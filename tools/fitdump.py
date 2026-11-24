#!/usr/bin/env python3
"""Minimal FIT/FDT parser: list sub-images and their component data."""
import struct
import sys


def parse_fdt(d):
    magic = d[:4]
    assert magic == b"\xd0\x0d\xfe\xed", "not an FDT"
    (_tot, off_struct, off_str) = struct.unpack(">III", d[4:16])
    p = off_struct
    strings_base = off_str
    path = []
    props = []   # (path, name, value)

    def u32():
        nonlocal p
        v = struct.unpack(">I", d[p:p + 4])[0]
        p += 4
        return v

    while True:
        tok = u32()
        if tok == 1:
            name = b""
            while d[p] != 0:
                name += d[p:p + 1]
                p += 1
            p = (p + 4) & ~3
            path.append(name.decode())
        elif tok == 2:
            path.pop()
        elif tok == 3:
            plen, nameoff = u32(), u32()
            value = d[p:p + plen]
            p = (p + plen + 3) & ~3
            end = d.index(b"\0", strings_base + nameoff)
            name = d[strings_base + nameoff:end].decode()
            props.append(("/".join(path), name, value))
        elif tok == 4:
            continue
        elif tok == 9:
            break
        else:
            raise ValueError(f"bad token {tok} at {p}")
    return props


def main():
    d = open(sys.argv[1], "rb").read()
    props = parse_fdt(d)
    for path, name, value in props:
        if path and any(k in name for k in
                        (" compression", "data-size", "data-position",
                         "load", "entry") ):
            print(f"{path or '/'}  {name} = {value.hex()} ({value!r})")
        elif name in ("description", "compatible"):
            if isinstance(value, bytes):
                v = value.split(b'\0')[0]
            print(f"{path or '/'}  {name} = {v!r}")


if __name__ == "__main__":
    main()