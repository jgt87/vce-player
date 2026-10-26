# VCEX support (2026-10-16)

VCEX is a ProfExam format, separate from Avanset VCE. Study Player now accepts
PV12 archives containing PRFEXV12 payloads through **Add exam** or
**Open VCE / VCEX / OEF**. **Inspect exam** reports encryption and readable counts.
Supported readable single/multiple-choice records can be practiced, scored and
saved/resumed. Embedded PNG prompt images are displayed locally; HTML is parsed
as text and never executed. Unsupported layouts, case studies, exhibits and
question types are excluded from scoring. Password-protected exams are rejected.
PV11 is not yet supported.

## Supplied file

`temp/Certified CPQ Specialist.Certified-CPQ-Specialist.ExamTopics.2026-10-15.244q.vcex`

- 1,891,540-byte archive; modified ZIP local signature `PV12`.
- One DEFLATE payload, 3,102,295 bytes, ZIP encryption flag unset; CRC verified.
- Payload header `PRFEXV12`; length-prefixed records start at byte 1033.
- 244 question records, 15 embedded images, no exam password.
- Questions 1–10 are readable base64 JSON; all ten import, including question 3's PNG.
- 234 records start with `*`. Their question, explanation and answer fields are encrypted.
- Stored passing score 850 and time 120 minutes are metadata, not used as the
  grading rules for a ten-question subset. Imported sessions are practice only,
  using the app's standard 70% practice threshold. The subset notice remains visible.

## Evidence

Official package: <https://profexam.com/download>, Linux
`ProfExam-Simulator-v10.deb.zip`, version 10.21.8.
The package was extracted for static inspection; the vendor app was not run.

`app.asar` SHA-256:
`739857459322abba22bb8a2338c578f92e7047e877230bd1767010d22f673002`.
REA inventory evidence `ev_59b02f05fef6aeafb9089019af82d7e598640b366ef241bafb3e7c4e94df7f3a`
records the shipped artifact without integrity contradictions. A separate narrow
main-process analysis (`ev_fa7fc90e7321bf422dff7f5bcd41a496a708e2f69d9dc31ed0d065bfa9185b26`)
has partial graph coverage and does not itself establish renderer semantics.

Direct static inspection of shipped `main.2b11658ea5c4bb22.js` establishes:

- `Uye.readerData`: V12 field order, images, question count, `*` protected-record marker.
- `Uye.readStringWithLength`: one byte gives the number of ASCII length digits,
  followed by that many payload bytes.
- `R8.fromData`, `R8.newDataQuestionSingle/Multi`, answer setters: x2 prompt,
  x3 explanation, x4 answer JSON; choice x1 is correctness, x3 is HTML.
- `j8._getAES128Transform`: AES-128-CBC, zero IV, first 16 bytes of SHA-256
  over the UTF-16LE content-key string. Fields decode as UTF-16LE after decryption.
- `D8.requestKey`: the activated vendor app requests a per-file private key
  from its activation service. That private key is not contained in this reader.

These are static observations, not evidence of successful authenticated key
retrieval. This implementation performs no activation requests, key retrieval or
decryption of protected fields. Full 244-question playback remains unsupported.

## Verification

`python3.11 analysis/inspect_vcex.py` reproduces the inventory.
`python3.11 analysis/validate_vcex.py` runs the unit suite and hidden-window checks
on the supplied file: library import, all ten questions, image rendering,
correct-answer scoring and persisted save/resume. Results:
`validation/vcex-support.json`.

The source file and vendor package are excluded from packaged app assets.
