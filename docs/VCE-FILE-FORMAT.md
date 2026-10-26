# `.vce` file format — what is established

Scope: the Player's read path for format value 31 (the bundled sample), recovered
by static disassembly and validated at runtime. Addresses are static VAs (image
base `0x400000`, no ASLR). This is a partial but validated specification, not a
complete serializer definition. See "Not yet established" at the end.

Format-62 continuation findings are in `FORMAT-62-PROGRESS.md` and
`LICENSED-PLAYER-FINDINGS.md`; its content encryption differs from this sample.

## 1. Container at a glance

- The bundled `Exam Sample.vce` is 591,185 bytes, whole-file entropy ≈ 7.9994
  bits/byte. It is **not** ZIP, gzip, SQLite, RTF, PNG or JPEG.
- Only the first 4 bytes are plaintext (the header). Everything after is produced
  by the per-field keystream in §3 (high entropy by construction).
- Content protection is the custom keystream only. OpenSSL is **not** on the
  content path (see `APPLICATION-ARCHITECTURE.md` → Network/crypto).

## 2. Header (offsets 0–3), validator `0x949060`

Read via the stream one-byte helper `0x638F84`. Logic, confirmed from assembly and
a runtime hook that fires on open:

```
b0 = read_u8(); b1 = read_u8();
require b0 == 0x85 and b1 == 0xA8            # else "not a VCE file" error
b2 = read_u8(); b3 = read_u8();
format = b2*10 + b3                           # stored at reader+0x38
if format > 63: raise "newer format" error
```

| Offset | Sample | Meaning |
|---|---|---|
| 0–1 | `85 A8` | Signature |
| 2–3 | `03 01` | `format = 3*10 + 1 = 31` (conventionally "3.1") |
| 4…  | keystreamed payload | §3 |

`format` is the **file-format value**, not the product version. Loader `0x949FD8`
routes values 40 and 42–45 to an "older format" message and contains further
version-specific dispatch; the metadata reader selects a 31–34 branch at
`0x92A076`.

## 3. Field de-obfuscation — the keystream (fully recovered & validated)

Each field is read by a decoder (`0x63A370` is a **length-prefixed string/blob
reader**: a seed, then a keystreamed 4-byte little-endian length, then that many
keystreamed data bytes — one continuous keystream for the whole field). The decode
is a **self-keyed byte stream**: the plaintext feeds back into the keystream.

```
seed = read_u8()                              # per-field nonce
k    = g(0x80, f(seed, seed ^ 0x80), 0)       # initial keystream byte
for i = 0,1,2,...:                            # until field length consumed
    c = read_u8()                             # ciphertext byte from stream
    p = c XOR k                               # plaintext byte (emitted)
    k = g(k, f(c, p), (i & 0xFF) + 1)         # advance keystream
```

The two callbacks are installed for format 31 by initializer `0x63A780` into
globals `[0xB134D4] = f = 0x638A2C` and `[0xB134CC] = g = 0x638A40` (verified at
runtime once a format-31 file is decoded):

```
f(a,b) = (((a XOR b) OR 1) * (((a + b) AND 0xFF) XOR 1)) AND 0xFF
g(a,b,c) = (round_half_even(a * sin(b)) mod 256) XOR c      # b in radians; x87 FSIN
```

Implementation notes:
- `f` is pure 8-bit integer arithmetic (the IMUL is 16-bit but only the low byte
  is consumed). Validated **14/14** against live register traces.
- `g` uses the x87 `FSIN` (radians) then `FISTP` with the ambient rounding mode
  (round-half-even observed). Negative results are reduced mod 256 before XOR.
  Validated against live samples (e.g. `g(128,155,0)=144`, `g(144,15,1)=95`).
- Reconstruction shortcut used during analysis: in each loop `f(c, p)` call, the
  **EDX argument is the plaintext byte `p`**. Collecting EDX across `f` calls
  (skipping the per-field init where `a XOR b == 0x80`) reconstructs the decoded
  stream directly. This recovered the sample's metadata as `000-001` and
  `Exam Sample` with no further work.

### 3.1 On-disk string-field framing (validated)

A string/blob field is laid out as:

```
field = seed(1 byte) || E_seed( le32(length) ++ data[length] )
```

where `E_seed` is the keystream above, seeded from `seed`, index starting at 0 and
incrementing per byte across both the 4 length bytes and the `length` data bytes
(one continuous keystream per field). Strings are single-byte (Delphi AnsiString);
`length` is the byte count.

A reference codec implementing exactly this — `f`, `g`, `decode_field`,
`encode_field` — is at `analysis/phase3/codec/vce_codec.py`. It is validated two
ways: it **decodes** the bundled sample's fields (`000-001`, `Exam Sample`), and
`encode_field` **round-trips byte-exact** back to the original field bytes for
both fields. This proves the field codec; it is for understanding the format and
authoring one's own content, not for processing third-party files.

## 4. Metadata record — `TVCEFilePropertiesQ`

Reader `TVCEFileProperties.ReadFromStream = 0x928F60`; writer `WriteToStream =
0x92BF84`; `PassDataReading = 0x92C598` (authoritative encoder not yet analyzed).
Published fields, in RTTI order:

```
FFileName, FFileType, FExamNumber, FExamTitle, FPassingScore, FTimeLimit,
FFileVersion, FCreatedDateUnix, FCreatedTimeUnix, FModifiedDateUnix,
FModifiedTimeUnix, FCreatedDate, FCreatedTime, FModifiedDate, FModifiedTime,
FShowDescription, FUsePassword, FPassword, FReservedBlockStream
```

So a `.vce` carries an exam number, title, passing score, time limit, created/
modified timestamps (Unix and split date/time forms), a description flag, and an
**optional password** (`FUsePassword` / `FPassword`) — the format supports
password-protected files. At runtime, opening the sample decoded `FExamNumber`
(`000-001`) and `FExamTitle` (`Exam Sample`) and inserted them into the DB.

On-the-wire layout observed by instrumenting the real parse (offsets relative to
the start of the metadata record, i.e. file offset 4):

```
off 0 : 1 leading byte (0x00 in the sample) consumed before the fields
off 1 : string field  -> FExamNumber  (sample: "000-001", len 7)
...   : string field  -> FExamTitle   (sample: "Exam Sample", len 11)
...   : string field  (len 3 in the sample)
...   : 2 x 4-byte reads     -> integer fields (e.g. version / score / time limit)
...   : 4 x 8-byte reads     -> the four Unix timestamp fields
...   : 7 x 1-byte reads     -> flags / small fields (ShowDescription, UsePassword, ...)
```

The string-data bytes are fetched via a different stream method than the 1-byte
length reads, so a naive read-counter under-counts a field's size; use the field
codec (§3.1) to walk fields precisely.

### 4.1 Non-string fields (observed, not fully decoded)

After the keystreamed string fields, the demo sample's metadata region is
**low-entropy with clear little-endian numeric structure** (runs of `00` and `ff`),
unlike the high-entropy keystreamed strings. Example raw bytes right after the
title field: `… 50 00 00 00 00 bb 92 53 7c ff ff ff ff c0 47 0e 53 00 00 00 00 …`
— consistent with 4-byte integers and 8-byte (two-dword) timestamp values. The
runtime read pattern there was `2× 4-byte`, then `4× 8-byte`, then `7× 1-byte`,
matching the RTTI field group (two integers, the four Unix timestamps, the flag /
small fields). These trailing fields do **not** appear to use the per-field string
keystream; their exact encoding (raw little-endian vs. a light transform) and the
field↔RTTI-name mapping were not conclusively determined. This is metadata-record
structure only — it is orthogonal to the content/consistency gate in §6.

## 5. Record / content model

A `.vce` contains a sequence of typed records. Factory `0x945274` maps a type byte
to a class: **type 0 → `TExamRef`**, **type 1 → `TCaseStudyExamRef`** (names
resolved from the VMTs at runtime); any other value raises `UNKNOWN_EXAM_TYPE`.
The record loop `0x949B98` reads records, dispatching by a discriminator at
`self+0x38` (the format value) through per-range readers:

| Discriminator | Reader |
|---|---|
| 0x15–0x16 | `0x63968C` |
| 0x1F–0x22 (31–34) | `0x63A370` (the §3 integer decoder) |
| 0x3C | `0x8527A0` |
| ≥0x3D | `0x852850` |

Domain classes present (from RTTI; 35 `TVCE*` total): `TVCEQuestionSet`,
`TVCESection` / `TVCESectionCollection`, `TVCETestlet`, `TVCELabCollection`,
`TVCEFilePropertiesQ`, `TVCEStreamProcessorR` (the stream/decode engine),
`TVCEReaderR`, `TVCEHistoryItemC`, `TVCEExamLaunchOptions`. The localization
resources name eight question types: multiple choice, fill in the blank, select
and place, point and shoot, hot area, create a tree, build list and reorder, drop
and connect.

Question content decodes **only when an exam is started** (not when added to the
list): at add time only the §4 metadata is read (confirmed at runtime).

## 6. Load-time validation (`INVALID_FILE_FORMAT`)

The Player validates a file beyond the header. The localization key
`INVALID_FILE_FORMAT` ("Invalid file format or corrupted file.") is referenced in
two places:

- the header validator `0x949060` (signature / version-value failure, §2), and
- the **start-time exam loader `0xA5D038`** (references at `0xA5D608` and
  `0xA5DA90`).

Observed behavior: a file with a correct header and a correctly-encoded metadata
record is **added to the exam list** (metadata parse succeeds), but the loader
rejects it with `INVALID_FILE_FORMAT` when the exam is actually opened/started if
the full content does not pass the loader's format/consistency validation. In
other words there is a second validation gate at load time, separate from the
header and metadata parse.

This document records that the gate **exists** and where it lives. It intentionally
does not characterize how to satisfy it for an arbitrary hand-built or modified
file: that is the capability needed to tamper with or fabricate `.vce` files
(including unauthorized exam-dump content), and it is out of scope here. The
legitimate authoring path for new content is the vendor's Designer.

## 7. Not yet established

- Exact framing of the non-string field readers (integer/timestamp/flag) and the
  overall record/section/question layout and ordering. (String/blob field framing
  **is** established — §3.1.)
- Per-question-type serialization (the eight types above).
- The precise content/consistency rule enforced by the §6 loader gate (not pursued
  — see note above).
- The authoritative encoder: `designer.exe`'s `WriteToStream` methods were not
  analyzed. They are the correct source for a precise write specification.
