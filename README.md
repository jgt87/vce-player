# VCE Exam Simulator — Reverse-Engineering Documentation

## Testable GUI application

The workspace now includes **Study Player**. Open `dist/StudyPlayer.exe` or
double-click `Launch Player.cmd` to run from source. See
[running and functional validation](docs/RUNNING-THE-APP.md).

VCEX (ProfExam PV12) inspection and readable-choice practice are supported.
The supplied CPQ file has 10 readable and 234 encrypted questions; all 10 readable
questions can be practiced, with embedded prompt images and saved progress.
Full encrypted-content playback is unavailable. See [VCEX support](docs/VCEX-SUPPORT.md).

Open Exam Suite `.oef` files are supported in current protobuf and legacy NRBF
formats, including sections, images, single/multiple answers, timed sessions,
scoring and saved progress. Choose **Add exam** to import one.
The OEF-enabled build is `dist/oef/StudyPlayer.exe`.
See [OEF support](docs/OEF-SUPPORT.md).

Native VCE compatibility is partial: the supplied example maps to 206 records,
with 18 complete content records decoded and a smaller practice subset. Scored
practice now covers every native type whose grading semantics are established
from recovered data: textual single/multiple choice (types 0/1), single-blank
case-insensitive fill-in-the-blank (type 8), reorder-list (type 5), connect
(type 7), and the image-coordinate types point-and-shoot (type 3) and hotspot
(type 9) — the last two whenever a renderable PNG can be recovered from the
image field, with rects graded in image-pixel space. Only drag-and-drop (type 2)
and tree (type 4) remain unscored: their placement/hierarchy-to-answer mapping is
not established, so they are shown in the native view, not graded.
See [licensed Player findings](docs/LICENSED-PLAYER-FINDINGS.md) for the remaining
authenticated content-key requirement. The historical crypto conclusions below
apply to the original format-31 demo research, not all VCE versions.

A static + bounded-runtime study of the **VCE Exam Simulator** demo (a Delphi/VCL
Windows app, `player.exe`), documenting its architecture and the `.vce` file
format for interoperability and research. It does **not** reproduce the
application, bypass its licensing, or process third-party exam-dump files.

## Key findings

- `.vce` header is 4 bytes: `0x85 0xA8` signature + a version value `b2*10 + b3`
  (rejected if > 63). Validated on two independent files.
- Field content is obfuscated with a custom **self-keyed byte keystream**
  (callbacks `f` and `g`), recovered and validated byte-exact.
- Local data is **plain SQLite** (`vcesimulator.db`); some config BLOBs are raw,
  some lightly obfuscated.
- OpenSSL **AES-128-GCM is only the app's TLS network transport**, not file
  protection — exam content uses the keystream, not OpenSSL.
- A **load-time integrity gate** exists in the exam loader (`0xA5D038`,
  `INVALID_FILE_FORMAT`): documented, intentionally **not** bypassed.
- **Security model**: no strong file-level cryptography — content is *keyless*
  obfuscation (security-by-obscurity); the real enforcement (valid-file check,
  licensing) is application-level. See `docs/APPLICATION-ARCHITECTURE.md` §6.

## Contents

- **HANDOVER.md** — entry point: scope/boundary, status, repository map, one-minute reproduction.
- **docs/VCE-FILE-FORMAT.md** — header, version dispatch, keystream algorithm + codec, metadata/record model, the integrity gate.
- **docs/APPLICATION-ARCHITECTURE.md** — class model, start/run call chain, static-only functions, SQLite schema + BLOBs, network/crypto (AES=TLS).
- **docs/RUNTIME-VALIDATION.md** — methodology, evidence index, validation matrix, tooling gotchas.
- **analysis/phase3/codec/vce_codec.py** — validated reference codec for the keystream field format (decode + round-trip encode).
- **analysis/** — full evidence trees (Phase 1–3 REA dossiers and Frida captures).

## Scope & legal

For interoperability, security research, and education on a locally installed
demo. `.vce` files circulating as "exam dumps" are typically unauthorized copies
of real certification questions; do not use this material to pirate exam content
or to circumvent the product's licensing. See `HANDOVER.md` → Scope / Legal.
