"""VCE format-31 field codec (keystream), reverse-engineered & validated.
Decoder is validated by recovering the bundled sample's metadata.
Encoder is the exact inverse. Original-content authoring / interop only.
"""
import math, sys

def f(a, b):
    return ((((a ^ b) | 1) * ((((a + b) & 0xFF) ^ 1))) & 0xFF)

def g(a, b, c):
    r = round(a * math.sin(b))          # round-half-even, b in radians (x87 FSIN/FISTP)
    return (r % 256) ^ (c & 0xFF)

def _init_k(seed):
    return g(0x80, f(seed, seed ^ 0x80), 0)

def decode_field(buf, pos):
    """Decode one length-prefixed string field at buf[pos]. Returns (seed, length, data, newpos)."""
    seed = buf[pos]; pos += 1
    k = _init_k(seed); idx = 0
    lenb = bytearray()
    for _ in range(4):
        c = buf[pos]; pos += 1; p = c ^ k; lenb.append(p)
        k = g(k, f(c, p), (idx & 0xFF) + 1); idx += 1
    length = int.from_bytes(bytes(lenb), 'little')
    data = bytearray()
    for _ in range(length):
        c = buf[pos]; pos += 1; p = c ^ k; data.append(p)
        k = g(k, f(c, p), (idx & 0xFF) + 1); idx += 1
    return seed, length, bytes(data), pos

def encode_field(data, seed=0x00):
    """Encode a string field: returns bytes = seed || keystream(le32(len) ++ data)."""
    payload = len(data).to_bytes(4, 'little') + bytes(data)
    out = bytearray([seed & 0xFF])
    k = _init_k(seed); idx = 0
    for p in payload:
        c = p ^ k; out.append(c)
        k = g(k, f(c, p), (idx & 0xFF) + 1); idx += 1
    return bytes(out)

DEFAULT_SAMPLE = r"C:\Program Files (x86)\VCE Exam Simulator Demo\samples\Exam Sample.vce"

def selftest(path=DEFAULT_SAMPLE):
    buf = open(path, 'rb').read()
    print("header:", buf[:4].hex(), " format =", buf[2] * 10 + buf[3])
    pos = 5  # offset 4 is a leading byte consumed by the metadata reader before the fields
    for i in range(4):
        try:
            seed, length, data, npos = decode_field(buf, pos)
            if not (0 < length < 4096):
                raise ValueError("implausible length")
        except (IndexError, ValueError):
            print(f"field#{i} @off {pos}: not a decodable string field -> non-string field type begins here; stopping")
            break
        assert encode_field(data, seed) == buf[pos:npos], "encode round-trip mismatch"
        print(f"field#{i} @off {pos}: seed={seed:#04x} len={length} span={npos-pos}B data={data.decode('latin1')!r}  [round-trip OK]")
        pos = npos
    print("done: string-field codec decodes and round-trips the sample's metadata.")


def _check_header(path):
    b = open(path, 'rb').read(4)
    fmt = b[2] * 10 + b[3]
    ok = b[0] == 0x85 and b[1] == 0xA8 and fmt <= 63
    print(f"{path}\n  signature {b[0]:#04x} {b[1]:#04x}  format={fmt}  -> {'VALID header' if ok else 'INVALID header'}")
    return ok

def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="VCE format-31 field codec (interop / original-content authoring only).")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("selftest", help="decode + round-trip the bundled sample")
    s.add_argument("path", nargs="?", default=DEFAULT_SAMPLE)
    h = sub.add_parser("header", help="validate a .vce header (any version)")
    h.add_argument("path")
    d = sub.add_parser("decode-field", help="decode one format-31 string field at an offset")
    d.add_argument("path"); d.add_argument("offset", type=lambda x: int(x, 0))
    e = sub.add_parser("encode-field", help="encode a format-31 string field (prints hex)")
    e.add_argument("text"); e.add_argument("--seed", type=lambda x: int(x, 0), default=0)
    args = ap.parse_args()
    if args.cmd == "header":
        _check_header(args.path)
    elif args.cmd == "decode-field":
        buf = open(args.path, 'rb').read()
        seed, length, data, npos = decode_field(buf, args.offset)
        print(f"seed={seed:#04x} len={length} end={npos} data={data!r}")
    elif args.cmd == "encode-field":
        print(encode_field(args.text.encode('latin1'), args.seed).hex(' '))
    else:  # default: selftest
        selftest(getattr(args, "path", DEFAULT_SAMPLE))

if __name__ == '__main__':
    _cli()
