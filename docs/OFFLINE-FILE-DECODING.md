# Offline VCE file decoding

Later document parsing improvements are recorded in `RICHVIEW-DECODING-PROGRESS.md`.
The exports were regenerated: previously unsupported -9/list controls and text
encoding boundaries are now decoded for this corpus, with four JPEG validation
limitations remaining. Historical warning counts below have been superseded.

The standalone command reads the supplied files directly and writes JSON,
readable recovered text, and binary assets. It does not launch the vendor
application or contact a license service.

```powershell
python vce_decode.py 'temp/*.vce' --output decoded
```

Open `decoded/README.md` for links to each file's exports. Each export directory
contains `exam.json`, `questions.txt`, and `assets/`. The source files remain
unchanged. Binary assets retain decoded field bytes even when their internal
document layout is only partially understood. The export references initial
and encoded key blocks by source offset, length, and hash rather than copying
key material into the readable output.

## Results on the supplied files

| File | Format | Mapped records | Structurally decoded records |
|---|---:|---:|---:|
| Amazon SAA-C03 | 62 | 7 | 5 |
| CompTIA SY0-701 | 62 | 7 | 5 |
| Databricks Data Engineer Professional | 62 | 7 | 5 |
| Exam1 | 63 | 1 | 1 |
| Microsoft AZ-104 | 62 | 206 | 18 |

There are 228 mapped records and 34 structurally decoded records. Structural
success does not imply complete RichView rendering or exam scoring. The format-63
sample contains a blank question with four blank choices; no nonempty question
text was recovered from that sample. The other four files have recovered text,
with explicit warnings for unsupported RichView styles (notably style -9) and
some text-encoding cases. Raw decoded fields are retained for further analysis.

Protected fields remain encrypted because their selected pool is absent. This
file-decoding pass does not remove that cryptographic dependency; it produces
an inspectable representation of the recovered fields and remaining boundaries.

## Modern container map

The format-62 and supplied format-63 sample share this observed order:

1. Signature `85 a8`, then two format bytes; value is `b2*10+b3`.
2. Little-endian 32-bit container/key version (observed 4).
3. Five-byte encoded length, followed by the initial 1024-byte pool.
4. Five-byte encoded length, followed by the opaque wrapped key block.
5. Flags byte, encrypted exam number/title, raw score/time integers,
   encrypted file version, and two raw 64-bit timestamps.
6. Encrypted styles and description, observed raw zero, encrypted auxiliary field.
7. Raw top-level reference count, then reference/question records.
8. A 12-byte trailing area in all five supplied files.

The existing AES field structure is a seeded length, marker, key offset, and
block ciphertext. The marker selects the initial or protected pool. Each
question's common field framing is exported independently even when its
identity fails to decrypt, so an unavailable record does not hide subsequent
field offsets.

## New format-63 evidence

Source: `temp/Exam1.vce`, SHA-256
`9697feceb8dd8097c0a83aac9c63068a9a7aa07ed5f3e151999cff0c74629486`.

- Initial pool: file offset 13, length 1024.
- Encoded key block: offset 1042, length 1280. No claim is made that its
  plaintext payload matches the format-62 Designer's 2052-byte wrapper input.
- Metadata: offset 2322 through 2425.
- Top-level reference count: offset 2939, value 1.
- Reference envelope: five-byte length at 2943, payload size 416, end 3364.
- Unlike the observed format-62 references, this top-level reference has an
  additional outer length envelope before its type byte.
- Its plain question list contains one type-0 record, with four choices.
- The record parser reaches the envelope end exactly, leaving 12 trailing bytes.

Support is limited to this observed plain-reference layout and synthetic
fixtures. Format-63 nested references are explicitly rejected pending evidence;
the reader does not guess their schema.

## Trailing area finding

For every supplied file, the first four trailing bytes interpreted as a
little-endian integer equal the exact total file size, including the trailer.
That interpretation is reported along with a match flag. The remaining eight
bytes are opaque. They do not equal the simple CRC32-of-prefix value tested;
no checksum algorithm or authentication meaning has been established.

## Validation and scope

All 92 regression tests and the GUI smoke test passed. New fixtures exercise
format-63 extent consumption/truncation and offline exports, including source
preservation, binary-asset hashes, recovered text, and unavailable-field labels.
All five real files were exported successfully. The regenerated corpus report
includes format 63; 45 candidate-pool combinations recovered no additional
structurally valid protected prompts.

This pass changes the source parser and adds a source CLI. The packaged GUI
executable was not rebuilt, in keeping with the requested file-decoding focus.
