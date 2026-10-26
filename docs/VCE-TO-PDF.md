# VCE to PDF conversion

Five PDFs were generated from the files in `temp/`, using the offline decoder.
They include recovered question/choice text, stored textual answers,
explanations, case-study context, and supported source images. Original
question numbers are preserved. Missing protected records are summarized
explicitly; these are recovered-content PDFs, not complete decrypted exams.

| PDF | Pages | Decoded / source records |
|---|---:|---:|
| Amazon-SAA-C03-recovered.pdf | 7 | 5 / 7 |
| CompTIA-SY0-701-recovered.pdf | 7 | 5 / 7 |
| Databricks-Data-Engineer-recovered.pdf | 8 | 5 / 7 |
| Exam1-recovered.pdf | 2 | 1 / 1 (blank source record) |
| Microsoft-AZ-104-recovered.pdf | 35 | 18 / 206 |

Final files are in `output/pdf/`. The converter is `vce_to_pdf.py`.
PDF dependencies were installed locally under `.tools/pdf-packages` rather
than modifying the application requirements or global Python installation.

The two decoded AZ-104 image-question records also contain nested RichView
wording and PNG/JPEG answer-area images in their type-specific fields.
Those were included, increasing coverage beyond the earlier text-only export.
Their binary answer-region selections are not translated into guessed answers.
Other recovered diagrams, tables, and code screenshots are embedded as images.

Validation:

- Reopened each PDF with pypdf and verified every decoded question heading.
- Rendered every page with PyMuPDF and reviewed contact sheets and full-size
  representative pages, including image questions and case-study context.
- All text bounding boxes stay inside their pages; no layout overflow detected.
- Refined long case-study pagination and rerendered final PDFs for review.

Conversion status and source hashes: `output/pdf/conversion-report.json`.
Render/boundary checks: `output/pdf/render-validation.json`.

Reproduce:

```powershell
python vce_to_pdf.py
python analysis/compatibility/render_pdf_review.py
```

No source VCE file was changed. The protected key-pool limitation still applies.
