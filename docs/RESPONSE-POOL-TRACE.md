# Response pool and cache trace — 2026-10-15

Target: installed full `player.exe`, SHA-256
`4a112c2b9cfb2bfc5de39f62ce2739227e878a5f8ebae3289ab9e6d06d96e155`.
This extends `KEY-REQUEST-TRACE.md` with static evidence and file correlation.
No authenticated response was observed, and no additional exam was decrypted.

Follow-up: `PROTECTED-POOL-WRAPPING.md` locates the installed Designer's
protected-pool creation and RSA public-key wrapping algorithm. The matching
private key and successful unwrapping remain unavailable.

## Field marker selects the pool

The full Player's `0x855480` reads the field length and marker, then branches:

| Marker | Branch | Global slot | Meaning |
|---|---|---|---|
| `< 0x80` | `0x8554bf` | `0xb43d4c` | Initial file pool |
| `>= 0x80` | `0x8554ad` | `0xb43d50` | Response/content pool |

Both branches call `0x8551c0`. It reads the field offset, seeks the selected
pool, reads 32 key bytes and 16 IV bytes, then performs the established cipher
operation. The marker is not an ignored random byte. Its low seven bits do
not affect pool selection in this wrapper.

The global-pointer references connect the earlier reader and response code:
`0xb1db78` points to slot `0xb43d4c`; `0xb1cbd0` points to `0xb43d50`;
`0xb1d1c4` points to the separate active/writer slot `0xb43d48`.
The initial file-pool load writes through the first pointer, the response/cache
paths fill the second stream, and the reader explicitly chooses between them.
The writer `0x8554e4` corroborates the marker convention: when its active pool
equals the initial pool it emits a random marker below 128; when it equals the
response pool it adds 128 to that marker.

This explains why some protected offsets fit within 1024 bytes yet fail when
tested against the initial pool: they address an entirely different pool.

## Correlation with supplied files

The marker-aware audit checks identity, prompt, and answer fields:

| File | Initial-pool fields | Protected-pool fields | Decoded records |
|---|---:|---:|---:|
| Amazon SAA-C03 | 15 | 6 | 5/7 |
| CompTIA SY0-701 | 15 | 6 | 5/7 |
| Databricks | 15 | 6 | 5/7 |
| Microsoft AZ-104 | 54 | 564 | 18/206 |

All initial-pool common fields decrypt. The other fields explicitly select the
missing protected pool. AZ-104 question 6 markers are 189 (identity), 129
(prompt), and 243 (answer), all selecting the response pool. Question 5's
corresponding markers are 1, 104, and 58, selecting the initial pool.

## Response encoding

`0x81c628` is a Base64 stream encoder: it maps three bytes into four six-bit
alphabet indices, emits `=` padding, and inserts CRLF after 76 output columns.
Its primitive is `0x81c51c`; inverse primitive `0x81c5a0` and stream decoder
`0x81c7f8` reverse that mapping.

The callback's success path passes returned text through `0x81c7f8` into the
response stream. For versions >=52, `0xae7a56` onward reads a four-byte length
and copies that many subsequent bytes into a temporary stream, then replaces
the response stream with those bytes. `0x854e78` performs the analogous
length-prefix removal before storage. The precise interpretation of any
remaining response bytes is not established here.

Base64 is transport encoding, not a local substitute for the server's missing
key computation. The client-side path does not expose how the service obtains
the decoded pool from the encoded exam-key block.

## Cache storage

Insert `0xae5d20` and update `0xae65cc` call `0xae5614` for both encrypted-key
and decoded-key strings before constructing SQL. Lookup `0xae5fa4` applies the
same transformation to its lookup input and the retrieved decoded-key field.
The table is `exam_key_cache`.

`0xae5614` converts strings into streams, obtains a mask from `0x63d588`, and
calls `0xae5554`. That inner loop XORs data bytes with repeated mask bytes; it
is an involution at the byte level. The mask builder concatenates three results
from `0x63a234` with selectors 1, 2, and 3, converts case, and has an empty-value
fallback. Selector 1 explicitly executes CPUID. The exact sources of selectors
2/3 and all string-encoding edge cases remain unresolved. It would be premature
to claim a portable cache decoder has been validated.

The cache transformation requires an existing returned key to store. It does
not derive a protected exam pool from the preview pool. The prior read-only
schema check found no matching key-cache table in this installation.

## Implementation and validation

`Reader` now preserves an initial pool and a separate optional protected pool;
the marker chooses between them. `read_container(content_pool=...)` supplies
only the protected pool and no longer replaces the initial pool. This fixes an
incorrect assumption in the previous optional-pool interface.

Synthetic tests cover correct/wrong/missing protected pools, marker boundary
128, initial fields remaining independent, and mixed preview/protected records.
The corpus audit was regenerated, including the 28 candidate-pool trials using
the correct selector. No trial recovered an additional structurally valid prompt.
All 88 regression tests and the Tk GUI smoke test passed after preserving both
pools through the bounded native type reader.

Static evidence files under `analysis/licensed/`:

- `pool-global-references.json`: bounded byte-reference candidates and pointer slots.
- `pool-selection-windows.json`: marker branch, writer convention, mask builder.
- `response-codec-windows.json` and `base64-primitives.json`: transport and AES consumer.
- `response-processing-windows.json`: cache loop, insert/update and pool normalization.

These are bounded linear disassemblies, not complete control-flow proofs or
successful authenticated execution. Function conclusions above refer to
explicit instruction sequences; windows can also contain later routines/data.
