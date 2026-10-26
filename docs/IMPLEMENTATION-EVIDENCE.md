# Research reuse and compatibility ledger

The implementation uses the existing research in this workspace. The research
is partial; this ledger separates established behavior from original decisions.

| Source | Finding reused | Implementation / remaining gap |
|---|---|---|
| HANDOVER.md; docs/APPLICATION-ARCHITECTURE.md | Library, launch, session, history lifecycle | player.py; exam_engine.Store |
| analysis/phase2/database-schema.json; sample-db-metadata.json | Candidate identity, elapsed time, scores, sections, marked/incomplete counts; sample metadata | Stored result JSON and session state; independent database, no vendor BLOB compatibility |
| analysis/english-common.txt; english-player.txt; resource-index.json | Candidate, sections, review, training mode, eight question types | Candidate entry, section results, question review; two original question types supported |
| analysis/phase3/codec/vce_codec.py; build.py | Seeded field codec, first two strings at offset 5 for bundled format-31 sample | vce_inspector.py imports the existing codec directly; bounded 8192-byte prefix and round-trip checks |
| analysis/phase2/format31-helpers.md and disassembly; phase3/frida/probe2.jsonl; probe3.jsonl | Byte transform arithmetic and runtime metadata observations | Inspector tests use the documented live vectors; numeric model remains host sine / round-half-even |
| analysis/15-format-validator.json; phase3/02-header-asm.out.json | Signature and version formula | Inspector header checks; does not assume every version <=63 is supported |
| analysis/28-metadata-assembly.json; 30-metadata-assembly-rest.json; phase2/missing-methods-disassembly.txt | Version-dependent metadata and question readers | Format 62 uses 0x852850, not the recovered format-31 codec; additional analysis required |
| analysis/phase3/frida/probe5.js and probe5.jsonl | Metadata stream read observations | Timing starts after hook installation, values are null, cumulative offsets exceed file size; these are not reliable absolute file offsets |
| analysis/REPORT.md; phase3/PHASE3-FINDINGS.md; docs/RUNTIME-VALIDATION.md | Historical findings and later corrections | Final docs supersede early claims about missing methods and OpenSSL role; TLS is separate from exam content |
| analysis/sample-format.md | Sample identity and TXT/RTF import conventions | Bundled sample validation; TXT/RTF parser and full binary question serialization still absent |
| rea-session.mjs; configure-rea.ps1; analysis/phase3/run-batch*.mjs | Existing analysis tooling | Reused saved evidence first; connected REA for focused new format-62 reader analysis |

## Validation performed during implementation

The existing research codec was run read-only against the installed bundled
sample: exam number `000-001`, title `Exam Sample`, byte-exact field round trips.
This provides more framing detail than the handover's general unresolved-framing
note, but only for the first two sample metadata strings. The question layout
and the remaining metadata are still unresolved.

The user-supplied compatibility target in `temp/` has format value **62** and is
**6,809,328 bytes**. The native reader now decodes its metadata, maps 206 record
envelopes across six groups, and decodes 18 complete content records. Full
protected-content decoding remains unavailable. See `LICENSED-PLAYER-FINDINGS.md`
for later work and `RUNNING-THE-APP.md` for the testable GUI.

The research make.py script changes two sample metadata strings and retains the
vendor payload; it is not an original full-file serializer and is not used to
claim file authoring support.

Original design choices: JSON question format, equal-weight scoring, case-folded
text matching, SHA-256 identities, paused saved timers, and Tkinter interface.
These must not be attributed to recovered vendor behavior.
