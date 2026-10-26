# Open Exam Format support

Study Player reads `.oef` files from
[Open Exam Suite](https://github.com/bolorundurowb/Open-Exam-Suite).
The OEF-enabled executable is `dist/oef/StudyPlayer.exe`; the older executable
was running during the build, so it was left in place.
Use **Add exam** or **Open VCE / VCEX / OEF**, then select the imported library
entry and start or resume a session. **Inspect exam** shows OEF metadata.

## Supported data

- Current protobuf OEF and legacy NRBF OEF, without modifying the source file.
- Single and multiple correct answers, matched by option labels rather than positions.
- Section titles, explanations, instructions, question numbers and exam code.
- Timed sessions and untimed exams (`TimeLimit = 0`).
- The upstream pass mark on a 0–1000 scale. Scores use integer division,
  `correct * 1000 // total`, before comparison with that pass mark.
- Embedded PNG, JPEG, BMP, GIF and TIFF images, converted locally to PNG for display.
- `HideAnswers`: hides the practice answer-check action and explanations.

OEF is serialized data, not encrypted content. Legacy files are read by a
bounded data-only NRBF parser; no BinaryFormatter deserialization, .NET object
construction or assembly loading is used. Unsupported legacy record forms or
images produce an error rather than incomplete scored questions. File size is
limited to 64 MiB, exams to 10,000 questions and images to 20 million pixels.
Question/option content is displayed as text; Markdown styling is not rendered.

## Schema reference

Inspected upstream commit: `453c3cf31d611cf6ad9601ab8e4f1179f7569a8d`.
The importer is independently implemented from the published format contracts:

- [Core/Exam.cs](https://github.com/bolorundurowb/Open-Exam-Suite/blob/453c3cf31d611cf6ad9601ab8e4f1179f7569a8d/src/Libraries/Core/Exam.cs): protobuf field numbers and model types.
- [ExamIO/Utilities/Reader.cs](https://github.com/bolorundurowb/Open-Exam-Suite/blob/453c3cf31d611cf6ad9601ab8e4f1179f7569a8d/src/Libraries/ExamIO/Utilities/Reader.cs): protobuf/legacy detection and legacy property mapping.
- [Core/Services/Scorer.cs](https://github.com/bolorundurowb/Open-Exam-Suite/blob/453c3cf31d611cf6ad9601ab8e4f1179f7569a8d/src/Libraries/Core/Services/Scorer.cs): integer normalized-score semantics.

## Verification

The unit suite covers label mapping, packed/unpacked multiple answers, images,
normalized scoring, untimed/hidden-answer flags, malformed input and stable
save/resume identities.

`python3.11 analysis/validate_oef.py` additionally checks the downloaded upstream
samples in `temp/oef-upstream`: Basic Science protobuf (8 questions), Basic
Science legacy (8), and GMAT protobuf (20). Modern and legacy Basic Science
questions match, source hashes remain unchanged, and the GUI imports, scores,
saves and resumes each sample. A synthetic JPEG fixture checks desktop image
rendering and the hidden-answer setting. Report: `validation/oef-support.json`.

`python3.11 analysis/validate_oef.py --packaged` runs the packaged self-test,
including OEF protobuf import, JPEG rendering and scoring. Report:
`validation/packaged-oef-self-test.json`.

`python3.11 analysis/validate_oef.py --build` rebuilds `dist/oef/StudyPlayer.exe`.

Upstream source and samples are used for investigation and verification only;
they are not bundled into StudyPlayer.exe.
