#!/usr/bin/env python3
"""Regression check for the VCE RE package.

Runs with no third-party dependencies: validates the field codec by synthetic
round-trip, and (if the bundled demo sample is installed) decodes its metadata
and confirms byte-exact re-encoding. Prints PASS/FAIL and exits non-zero on fail.

Usage:  python verify.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "analysis", "phase3", "codec"))
import vce_codec as V  # noqa: E402

SAMPLE = r"C:\Program Files (x86)\VCE Exam Simulator Demo\samples\Exam Sample.vce"
fails = []


def check(name, cond):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        fails.append(name)


print("VCE codec regression check")

# 1. Callback vectors (from live register traces)
check("f(77,205)==155", V.f(77, 205) == 155)
check("f(151,7)==15", V.f(151, 7) == 15)
check("g(128,155,0)==144", V.g(128, 155, 0) == 144)
check("g(144,15,1)==95", V.g(144, 15, 1) == 95)

# 2. Synthetic round-trips
for seed in (0x00, 0x4D, 0xFF):
    for data in (b"", b"000-001", b"Sample Test Exam", bytes(range(40))):
        s, n, out, end = V.decode_field(V.encode_field(data, seed), 0)
        check(f"roundtrip seed={seed:#04x} len={len(data)}", out == data and s == seed and end == len(data) + 5)

# 3. Bundled sample (optional)
if os.path.exists(SAMPLE):
    buf = open(SAMPLE, "rb").read()
    check("sample signature 85 A8", buf[:2] == b"\x85\xa8")
    check("sample format == 31", buf[2] * 10 + buf[3] == 31)
    s0, l0, d0, p1 = V.decode_field(buf, 5)
    s1, l1, d1, p2 = V.decode_field(buf, p1)
    check("sample FExamNumber == '000-001'", d0 == b"000-001")
    check("sample FExamTitle == 'Exam Sample'", d1 == b"Exam Sample")
    check("sample re-encode byte-exact", V.encode_field(d0, s0) == buf[5:p1] and V.encode_field(d1, s1) == buf[p1:p2])
else:
    print("  [skip] bundled sample not installed")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
