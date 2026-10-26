# Android question schema comparison and implementation

The static Android 2.6.9 reader trace now supplies meanings for nested fields
that the Windows-derived reader previously preserved only as bytes. Acquisition,
hashes, REA Evidence and JADX coverage are recorded in
[OFFICIAL-ANDROID-APK-FINDINGS.md](OFFICIAL-ANDROID-APK-FINDINGS.md).

This pass reads the retained decompilation; it does not run the Android reader,
contact its license endpoint, or recover new keys. The new parsers are in
`question_schema.py`, integrated by `vce_container.py`. Semantic failures have
their own `schema_status`/`schema_error`; they do not erase recovered bytes or
change whether the original record was structurally decoded.

## Source map

All classes below are under
`analysis/licensed/official-android-jadx/sources/defpackage/`. `E10` is the
factory, and its numeric mapping is direct static evidence. The source-file
digests are retained in `analysis/compatibility/android-schema-source-hashes.json`.

| Type | Android class | Parsed meaning | Real recovered samples |
|---|---|---|---|
| 0 | C3344x10 / AbstractC1823g | Single choice | 31 |
| 1 | C3344x10 / AbstractC1823g | Multiple choice | 1 |
| 2 | F10 / N | Select and place: rectangles, source/target roles, placement values | None |
| 3 | D10 / H | Point and shoot: one correct-answer rectangle | None |
| 4 | C3520z10 | Tree roots, icons, flags, items, answer integers | None |
| 5 | C3167v10 | List items and correct index order | None |
| 7 | A10 | Connectors, boxes, normalized directed relationships, coordinates | None |
| 8 | B10 / r | Accepted strings; case, space and trimming flags | None |
| 9 | C10 / AbstractC3074u | Hotspot rectangles and correct-area flags | 2 |

Type 6 remains unsupported. The desktop factory's existing high-bit masking
remains unchanged; the Android factory itself uses exact numeric entries.
"No real recovered samples" means the schema has source and synthetic-test
coverage, not corpus or official-runtime confirmation.

## Common layout and document roles

The Android loader begins after the outer type and first integer. It skips
another integer and reads an exhibit count, then reads the two primary blobs.
This agrees with the existing three common integers followed by `prompt_data`
and `answer_data`; the third integer controls the optional exhibit blob.

`C3432y10` reads a seeded-length/raw RichView document from its nested stream.
For choice questions, `C3344x10.C` reads question, optional embedded case
context, each option, then explanation. `K1.b()` maps option indexes to `A`,
`B`, etc.; a character's presence in the stored answer identifies correctness.

For types 2, 3 and 9, the primary blobs describe interaction geometry, while
`image_data` contains the question and explanation documents; `image_aux_data`
is the image. For tree/list types, documents are in `tree_data`. For connect
questions, documents are in the first `connection_data` blob and coordinates
in the second. Fill-in-the-blank uses `prompt_data` for the two documents and
framed raw strings in `answer_data`.

Exports retain the original `prompt_documents` and all binary assets. They now
also include `question_schema`, correctly sourced `content_documents`, roles,
and an explicit document-count validation status. A raw structural decode does
not imply that every RichView item was rendered; existing rendering warnings
remain attached to each document.

## Interaction details and limits

- Rectangles use signed left/top/right/bottom coordinates, following the
  Android `Rect` constructor; width and height are not substituted.
- Type 2 reads a primary count and 21 bytes per place: rectangle, one-byte
  role (1 source / 2 target), and one integer. The answer stream's first
  integer is discarded by Android and is preserved as `answer_header` without
  assigning meaning. Each place then has an answer integer.
- Type 3 deliberately ignores the primary geometry blob, matching `D10`, and
  requires exactly four answer integers.
- Type 9 has separate rectangle and answer counts. Android uses their minimum;
  this decoder rejects unequal counts rather than silently discarding entries.
- Tree icon values and additional root/answer integers are retained numerically;
  no undocumented hierarchy or scoring interpretation is assigned.
- Reorder answers are bounds-checked indexes; duplicate indexes are retained
  because the static loader does not establish that repetition is invalid.
- Connector modes 0..4 follow `ConnectorInfo.b`. Endpoint order is normalized
  using the stored direction flag, matching `A10.y`. Endpoint and connector
  references are checked. Box and relationship coordinate counts follow their
  already parsed definitions; exact stream consumption is required.
- Count limits, remaining-byte checks, signed coordinates, truncation and
  trailing-byte rejection prevent semantic parsers from guessing layouts.

Android tree/list label methods use raw `t()` rather than encrypted `p()`.
`native_types.py` was corrected accordingly, including zero-length labels.
This fix is source/synthetic validated; supplied recovered records contain no
tree/list question to verify it against.

## Practice and validation

Practice mode now recognizes the optional embedded case document, keeps option
indexes aligned, and includes the recovered explanation. It requires exactly
the expected number of documents, rejects uncertain prompt/choice/context
rendering, and requires one stored answer for a single-choice question.
Session identity was bumped so old rendering assumptions cannot silently
resume into the new document mapping.

Scored practice has since been extended to every type whose grading semantics
are established here: single/multiple choice (0/1), single-blank
case-insensitive fill-in-the-blank (8), reorder-list (5, graded as an exact
sequence when the stored order is a clean permutation), connect (7, graded as an
unordered set of normalized box relationships), and the image-coordinate types
point-and-shoot (3) and hotspot (9). The player renders a reordering list, a
source/connector/target relationship builder, and image-canvas widgets
respectively. For 3 and 9 the question image is recovered from the image field
(raw PNG or a RichView-wrapped PNG, validated before use) and rendered at native
size, so rectangle coordinates in image-pixel space map 1:1 to clicks; a record
whose image cannot be recovered is left unscored. The image field's exact
wrapping is unverified, so this is validated on synthetic PNG fixtures only.
Drag-and-drop (2) and tree (4) remain unscored because their
placement/hierarchy-to-answer mapping is not established. No key acquisition is
added.

Validation:

- `python -m pytest -q`: 110 passed after the implementation changes.
- `python analysis/compatibility/audit_android_schema.py`: checks all five VCEs,
  writes `android-schema-audit.json`, and records per-file document-role counts.
- `python vce_decode.py 'temp/*.vce' --output decoded`: regenerates JSON/text
  exports with original input hashes retained.

Corpus structural coverage remains 34 / 228 records: five each from Amazon,
CompTIA and Databricks, one blank record from Exam1, and 18 from AZ-104. All
34 have a parsed semantic schema, including AZ-104 hotspots 32 and 71. This
does not unlock the other 194 records. Empty Exam1 content is still empty.

Remaining schema gaps include the exhibit bundle's detailed interpretation,
format-63 nested references, tree hierarchy/scoring semantics, and official
runtime corroboration for the interaction types without recovered samples.
