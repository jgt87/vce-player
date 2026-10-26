# Supplied VCE corpus comparison — 2026-10-15

All five `temp/*.vce` files were inventoried. The reproducible audit is
`python analysis/compatibility/compare_corpus.py`; its complete status/hash
report is `analysis/compatibility/corpus-comparison.json`. No decrypted exam
content or key bytes are exported by that script.

Follow-up: `RESPONSE-POOL-TRACE.md` establishes the marker's two-pool selection.
The comparison JSON now reports that selector explicitly and tests candidates
as the protected pool while preserving each file's original preview pool.

Later offline decoding supersedes the format-63 limitation below: the supplied
Exam1 plain reference and blank record now decode. See `OFFLINE-FILE-DECODING.md`
and `decoded/README.md`. The regenerated JSON includes five files and 45 trials.

| File | Format | Records mapped | Complete records decoded | Textual-practice subset |
|---|---:|---:|---:|---:|
| Amazon SAA-C03 | 62 | 7 | 5 | 0 |
| CompTIA SY0-701 | 62 | 7 | 5 | 1 |
| Databricks Data Engineer Professional | 62 | 7 | 5 | 0 |
| Microsoft AZ-104 | 62 | 206 | 18 | 4 |
| Exam1.vce | 63 | Unsupported | Unverified | Unverified |

“Complete records decoded” means the current structural record parser succeeds.
It does not establish full rendering or scoring support. The smaller practice
subset requires the current conservative text/layout checks to pass.

## Pattern found

All four format-62 files have the same header/container value, a 1024-byte
initial key pool, and a 2304-byte encoded key block. Their pool hashes and
encoded-block hashes are all different. Between pairs of initial pools there
is no shared starting byte, and only 2–9 of 1024 bytes match at the same
position. Those measurements do not establish a cryptographic derivation.

In each new seven-question file, questions 1–5 decode with that file's own
initial pool. Questions 6–7 fail due to unavailable or incorrect key material.
This repeats the five-question preview boundary seen in AZ-104's plain lists.
It is consistent with the previously traced service-backed content-key path.

We tested 28 candidate combinations: each format-62 target against the other
files' initial pools, and against every supplied format-62 raw second block
as a candidate pool. Each trial checks previously failed prompts for nested
RichView structure and also attempts the full container parser. None produced
an additional structurally valid prompt. Random padding success is recorded
separately and is not counted as decryption.

This rules out straightforward reuse of these supplied pools/raw second blocks
as tested; it does not prove that every possible offline derivation is absent.
No new full-content key or general decryption pattern was recovered.

## Compatibility fix

The new files use a top-level plain question list: title, question count, then
question envelopes. The earlier parser incorrectly consumed a nested-reference
tag before the question count. `vce_container.py` now consumes that tag only
for nested references. The three seven-question files can therefore be opened
in the native viewer, with questions 6–7 explicitly unavailable.

An original synthetic regression fixture covers this layout, verifies two
decoded records and exact end-of-file consumption, and preserves existing
nested-group/case-study tests. All 87 regression tests passed.

Exam1's header identifies format 63. Its metadata/question schema has not been
implemented or validated; it must not be presented as a corrupt format-62 file
or included in claims of successful decryption.
