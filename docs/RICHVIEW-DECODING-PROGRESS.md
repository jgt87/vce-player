# RichView decoding improvements — 2026-10-15

This pass improves interpretation of **already decrypted** documents in the
five supplied files. It does not recover the missing protected key pool.
Exports in `decoded/` were regenerated; start with `decoded/README.md`.

## Recovered layouts

- The exact observed header `-9 0 0 0 0 0 7` precedes another item header
  without a separate payload. The parser now consumes this control instead of
  stopping. Other -9 variants remain unsupported rather than being guessed.
- Some UTF-16 item bodies end in a Unicode paragraph separator immediately
  before the next ASCII item header. The previous parser recognized only ASCII
  CRLF boundaries and incorrectly included following control/header bytes in
  the UTF-16 body. It now recognizes both observed boundary forms.
- Text headers can contain a quoted hyperlink tag. The parser preserves these
  tags as links and continues reading the displayed text. It does not fetch URLs.
- Four observed ten-integer -11 list-control variants carry no separate payload
  before the following item header. The parser preserves their following text;
  it does not claim to reproduce the original list formatting.
- A scaled PNG has `width=...` and `height=...` ASCII properties between its
  graphic-class line and binary size. These bounded properties are consumed
  before the PNG size/payload, whose chunks and CRCs are validated as before.
- Four TJPEGImage payloads are now preserved and exported with `.jpg` extensions.
  The parser validates their framing and start/end markers, but retains an
  explicit warning because it does not implement full JPEG decoding.

## Measured result

The bounded prompt-document audit covers 188 documents across the supplied
decoded records, including empty documents. Its warning count fell from 143
to 4. Unsupported controls and text-encoding failures were eliminated in this
corpus. The four remaining warnings identify the JPEG validation limitation.

The audit's extracted-text count increased from 9,031 to 24,153 characters.
These counts include placeholders, so they measure export output rather than
an exact count of newly recovered semantic content. The old -9 failures often
produced only an unsupported-item placeholder; the new output contains the
following question, choice, and explanation text.

All six image files referenced by the final exports (two PNGs and four JPEGs)
were separately checked successfully using the installed Pillow image library's
`Image.verify()`. That verifies these actual exports; it does not remove the
standalone parser's validation warning for arbitrary future JPEG inputs.

There are still 34 structurally decoded records out of 228 mapped records.
This improvement recovers more readable content within those records; it does
not change the encryption boundary or turn protected records into plaintext.
The blank Exam1 record remains blank.

## Validation and remaining limits

All 97 regression tests and the Tk GUI smoke test passed. New original fixtures
cover the exact control header and an unknown variant, Unicode paragraph/header
boundaries, quoted links, list controls, scaled PNG framing, and explicitly
limited JPEG extraction. All five files were re-exported successfully.

Evidence:

- `analysis/compatibility/richview-audit-before.json`: baseline status/counts.
- `analysis/compatibility/richview-audit.json`: updated status/counts.
- `analysis/compatibility/audit_richview.py`: repeatable bounded prompt audit.
- `decoded/*/exam.json`: text, links, image asset references, warnings, and original
  decoded field assets for independent inspection.

Text item boundaries use observed header/delimiter framing; this is not a
complete RichView specification. Formatting/style semantics, arbitrary custom
items, and unobserved encodings may require further work. JPEG preview remains
dependent on the GUI's image support; offline image assets can be viewed directly.
The packaged GUI executable was not rebuilt in this file-decoding pass.
