# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope boundary (read first — this governs what work is acceptable)

This repo is a **static + bounded-runtime reverse-engineering study** of the VCE Exam
Simulator (a licensed Delphi/VCL Windows app) plus an original **Study Player** tool
that interoperates with the file formats. The following are hard constraints, not
preferences — see `HANDOVER.md` and `README.md` → Scope/Legal:

- **Do not** bypass licensing, the demo question limit, or the load-time integrity gate.
- **Do not** acquire or use the authenticated **content-key** — the 234 encrypted VCEX
  questions and undecoded native records are a licensing boundary that stays closed.
- **Do not** process third-party / pirated `.vce` "exam-dump" files for content
  extraction, nor commit anything decoded from them.
- **Never invent or guess scoring/parse semantics.** A feature is only built when the
  recovered evidence establishes its meaning. Validate exclusively against **synthetic
  fixtures** built in the tests, never against real dumps.

Concrete consequence of the last rule: native question types 2 (drag-drop) and 4 (tree)
are decoded and viewable but deliberately **not graded**, because their
placement/hierarchy→answer mapping is not established. Do not add grading for them
without new, cited reverse-engineering evidence.

## Commands

- Run the app: `python player.py` (or `Launch Player.cmd`). A PyInstaller build config is
  in `StudyPlayer.spec`; the OEF-enabled build lives under `dist/oef/` (both gitignored).
- Install deps: `pip install -r requirements.txt` (cryptography, Pillow). Note the live
  player renders images via Tk `PhotoImage` (**PNG only, no PIL**); Pillow is used by the
  OEF reader and some tests.
- Full test suite: `python -m pytest tests/ -q` — **always scope to `tests/`**. The repo
  root also contains `analysis/` with Unix-only tests (`import resource`) that fail to
  collect on Windows and are not part of the real suite.
- A single test: `python -m pytest tests/test_player.py -q` or a single case, e.g.
  `python -m pytest "tests/test_player.py::EngineTests::test_score_and_unanswered"`.
- Dependency-free regression: `python verify.py` (validates the format-31 field codec by
  synthetic round-trip; the extra vendor-sample checks run only if the bundled demo is
  installed locally).
- Real-Tk headless UI smoke (isolated temp DB, withdrawn root): `python tests/ui_smoke.py`.
- Packaged GUI self-test (what the shipped build runs): `python player.py --self-test-report <out.json>` then check `passed: true`.
- Offline decode/exports (local workspace only; needs `analysis/` + `temp/` inputs):
  `python vce_decode.py 'temp/*.vce' --output decoded`.

`verify.py`, `vce_inspector.py`, `vce_decode.py`, `tests/test_vce_inspector.py` and
`tests/test_vce_decode.py` import from the `analysis/` package (`analysis.phase3.codec.vce_codec`,
`analysis.compatibility.audit_encryption`). `analysis/` is **gitignored** (it also holds
licensed decompilation and vendored tooling), so it must stay present in the local tree —
a clean checkout of the published repo cannot run those five.

## Architecture

**Read pipeline (file → scored practice).** `.vce` header is `0x85 0xA8` + version
`b2*10 + b3`. Format **31** is the original Delphi demo (keyless, self-keyed keystream
codec, fully recovered in `analysis/phase3/codec/vce_codec.py`). Formats **62/63** are the
native (Android-schema) container:

- `vce_reader.py` — header/version dispatch and metadata.
- `vce_container.py` (`read_container`) — the orchestrator: walks format-62/63 records,
  decrypts the AES-CBC key-pool blobs via `native_types.py`, and decodes each record's
  nested documents and schema. Every record carries a `decoded` bool; `decoded_count`
  summarizes the container.
- `richview.py` (`parse_richview`, `parse_nested_documents`) — parses RVF documents into
  **text + images + links**. It intentionally does **not** interpret the per-run style
  table (bold/italic/etc.), because that format is unestablished — do not add rich-text
  rendering without recovering it first.
- `question_schema.py` (`parse_question_schema`) — per-type Android schema parsers
  (types 0–9); refuses records that are not fully decoded.

**Study Player (the GUI tool).**
- `exam_engine.py` — `load_exam` (imports + validates JSON / VCEX / OEF; **rejects raw
  `.vce`** because question framing is not established), `correct`/`score`, and the SQLite
  `Store` (tables `library`, `sessions`, `history`; sessions resume, history persists the
  full result JSON). Engine question types: `choice`, `text`, `order`, `connect`,
  `hotspot`, `point`. `order`/`connect` are JSON-authorable; `hotspot`/`point` carry a
  binary image and are native-only.
- `player.py` — the Tkinter app: library, timed/practice sessions, per-type input widgets,
  results, review, and result-history drill-down. Native sessions go
  `start_native → practice_exam → begin_session`, **bypassing `load_exam`** (binary-image
  types can't be authored as JSON).
- `native_study.py` — bridges decoded native-container records into a scored practice exam
  via a per-type `BUILDERS` dispatch. Promotes only the types with established grading
  semantics: 0/1 choice, 3 point, 5 reorder, 7 connect, 8 fill-in-blank, 9 hotspot.
  When grading semantics change, bump the resume-key tag (currently `native-practice-v3`)
  so stale sessions don't resume against new meaning.
- `native_view.py` — read-only Tk viewer for a native container (used for records that are
  decoded but not practiceable).
- Importers: `vcex_reader.py` (VCEX / ProfExam PV12), `oef_reader.py` + `oef_nrbf.py`
  (Open Exam `.oef`, both current protobuf and legacy NRBF).

**Testing model.** Tests import modules by top-level name and run from the repo root.
Fixtures synthesize encrypted containers end-to-end through `read_container`
(`tests/test_vce_container.py` exposes the builder helpers that other test modules and
`tests/ui_smoke.py` reuse). There is no real-dump dependency in the committed suite.

## Conventions

- Keep `CHANGELOG.md` `[Unreleased]` updated as each change is made.
- `docs/` holds the findings write-ups; `docs/ANDROID-QUESTION-SCHEMAS.md` is the source of
  truth for which native types have established grading semantics. Update it and `README.md`
  when native coverage changes.
