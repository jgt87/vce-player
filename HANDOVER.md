# VCE Exam Simulator (Demo) — Reverse-Engineering Handover

Date: 2026-10-14. Author handoff for continuation by another project/person.

This document is the entry point. It states the scope and boundaries, summarizes
what is established, maps the repository, and tells you exactly how to reproduce
the analysis. Detailed findings live in `docs/` and the `analysis/` evidence tree.

## Target

- Program: `C:\Program Files (x86)\VCE Exam Simulator Demo\player.exe` (the Player).
- SHA-256: `1e39a3e8a90242ee978c0e2779ac7ff0aa70c3399fbbc70e595de6a147826f6a`
- PE32 x86, image base `0x400000`, **no ASLR** (runtime delta `0`, so every static
  VA equals its runtime address). Built with Embarcadero Delphi (VCL).
- Ships with `designer.exe` (authoring tool), `sqlite3.dll`, and OpenSSL
  `libeay32.dll` / `ssleay32.dll`.
- Vendor: Avanset / Global Simulators Ltd. Commercial, licensed software.

## Scope and boundary (read before continuing)

This effort is a **static + bounded-runtime study to understand the application's
architecture and the `.vce` file format** — interoperability/security-research
work on a locally installed demo. Nothing in the installed product was modified,
and the Player's 5-question demo limit was never touched.

Explicitly **out of scope / not done** (and should not be inferred as pending):

- No reproduction/"full decompile" of the program into an equivalent executable.
- No bypass of the demo license limit and no replacement for the paid Player.
- No general decoder/extractor intended to consume third-party or pirated
  `.vce` "exam dump" content.
- No forging of any integrity/authenticity check the Player might enforce.

What **is** in scope and present here: the file-format structure, the content
de-obfuscation algorithm (validated on the vendor's own bundled sample), the
class/architecture model, the local database schema, and the network/crypto
characterization. A separate legitimate task — authoring an **original** example
`.vce` — was investigated but not completed (see "Open items").

## Status at handover

Resolved (with evidence):

- Application architecture (Delphi/VCL), class model, and file-open path.
- `.vce` header and version dispatch.
- Format-31 field **de-obfuscation algorithm**, fully recovered and validated
  byte-exact against live execution.
- Metadata record (`TVCEFilePropertiesQ`) field set.
- Record model: `TExamRef` / `TCaseStudyExamRef`.
- Exam start / run call chain, and the three previously-"missing" methods.
- Local SQLite schema (from the live DB).
- OpenSSL **AES-128-GCM = TLS transport** for a network/licensing call — **not**
  `.vce` content protection. (This resolves the Phase-2 "role unknown" note.)

Also resolved since first draft:

- The **string/blob field codec** is fully recovered and **round-trip validated**
  (reference impl `analysis/phase3/codec/vce_codec.py`). A file carrying original
  metadata encoded with it is accepted and listed by the Player.
- A **load-time validation gate** exists in the exam loader `0xA5D038` (raises
  `INVALID_FILE_FORMAT`): header+metadata can pass and the file be listed, yet the
  loader rejects it on open/start if full content fails its consistency check. Its
  location and behavior are documented; the precise rule was **not** reverse-
  engineered (satisfying it for arbitrary files is a file-fabrication capability,
  out of scope — see Scope).

Open items (future work, legitimate):

- Framing of the non-string field readers (integer/timestamp/flag) and the overall
  record/section/question layout. (String/blob framing is done.)
- Per-question-type serialization (eight types).
- `designer.exe` `WriteToStream` serializers were not analyzed (the authoritative
  encoder for authoring original content). REA's cached Ghidra project became
  unstable late in the session (see `docs/RUNTIME-VALIDATION.md` → Tooling
  gotchas); re-run from a clean project to continue.

Deliberately NOT pursued: reverse-engineering the `0xA5D038` validation so the
Player accepts arbitrary hand-built/modified files, and any analysis of
third-party exam-dump `.vce` files. Both are out of scope (see Scope / Legal).

## Not part of this package

The workspace also contains a **separate effort** — `player.py`, `exam_engine.py`,
`vce_reader.py`, `vce_inspector.py`, `tests/`, `examples/`,
`analysis/compatibility/`, `docs/IMPLEMENTATION-EVIDENCE.md`, and
`docs/FORMAT-62-PROGRESS.md` (a format-62 container / AES-256-CBC key-pool analysis
and a reader applied to a user-supplied third-party file). None of it is part of
this reverse-engineering documentation package: it was not written, reviewed,
validated, or endorsed here, and nothing in these docs depends on it.

This package is **only**: the RE documentation (`README.md`, `HANDOVER.md`,
`docs/VCE-FILE-FORMAT.md`, `docs/APPLICATION-ARCHITECTURE.md`,
`docs/RUNTIME-VALIDATION.md`, `docs/FUNCTIONS.md`, `docs/DIAGRAMS.md`,
`docs/SECURITY-DISCLOSURE-DRAFT.md`), the Phase 1–3 evidence under `analysis/`
(excluding `analysis/compatibility/`), the **format-31** reference codec
(`analysis/phase3/codec/`), and `verify.py`. Deliberately excluded: decoding of
format-62/63 content and any processing of third-party exam-dump files.

## Repository map

```
README.md                   ← one-page overview + key findings
HANDOVER.md                 ← you are here (scope, status, repo map, reproduction)
verify.py                   ← dependency-free regression check (run: python verify.py)
docs/
  VCE-FILE-FORMAT.md         ← header, version dispatch, keystream algorithm + codec, record model, integrity gate
  APPLICATION-ARCHITECTURE.md← classes, start/run chain, static-only functions, DB + BLOBs, network/crypto, security model
  FUNCTIONS.md               ← annotated address map (every key VA + role)
  DIAGRAMS.md                ← .vce layout, keystream, open-vs-start control flow
  RUNTIME-VALIDATION.md      ← methodology, evidence index, validation matrix, tooling gotchas
  SECURITY-DISCLOSURE-DRAFT.md ← high-level vendor note (no exploit; not sent)
analysis/
  REPORT.md                  ← Phase 1-3 narrative report (historical, detailed)
  phase3/codec/              ← format-31 reference codec (vce_codec.py) + tests (test_vce_codec.py)
  sample-format.md           ← bundled-sample byte observations
  *.json / player-*.json     ← Phase 1 REA evidence dossiers
  phase2/                    ← Phase 2 REA evidence + missing-methods disassembly
    missing-methods.md, format31-helpers.md, database-schema.json
  phase3/
    PHASE3-FINDINGS.md       ← runtime validation matrix + detail
    frida/                   ← Frida probes (probe*.js), runner (run.py), captures (*.jsonl)
    reqs2/, *.out.json       ← later REA batch requests/results
.tools/                      ← Ghidra 12.1.4, JDK 21, Frida venv (local, not committed upstream)
rea-session.mjs, run-batch*.mjs ← REA drivers
configure-rea.ps1, install-rea-prereqs.ps1 ← toolchain setup
```

## Reproduce in one minute

Prerequisites are staged under `.tools/` (Ghidra 12.1.4, Temurin JDK 21, a Frida
venv with frida-tools 17.x). See `docs/RUNTIME-VALIDATION.md` for full detail.

- Static (REA/Ghidra): set `GHIDRA_INSTALL_DIR` and `JAVA_HOME` to the `.tools`
  paths, drop request JSON files, and run `run-batch.mjs` (one-shot) or
  `rea-session.mjs` (persistent). Results are written next to the requests.
- Runtime (Frida): `.tools/frida-venv/Scripts/python.exe analysis/phase3/frida/run.py
  <seconds> arg <probe.js> "<path-to-.vce>"` spawns the Player under the probe and
  writes `<probe>.jsonl`. Kill stray `player.exe` first (single-instance app).
- Quick regression (no deps): `python verify.py` — checks the keystream callbacks,
  synthetic round-trips, and (if installed) the bundled sample's metadata. Prints
  `ALL PASS`. The codec unit tests: `python -m pytest analysis/phase3/codec`.

## Legal note

`.vce` files in the wild are frequently unauthorized copies of real certification
questions; the format and this software are the vendor's property. Use these
findings for interoperability, security research, and education. Do not use them
to pirate exam content or to circumvent the product's licensing.
