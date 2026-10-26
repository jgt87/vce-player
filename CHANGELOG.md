# Changelog

All notable changes to the Study Player tooling are recorded here. This file
tracks the player/reader workspace; the reverse-engineering documentation
package versions its findings in `docs/` and `analysis/`.

## [Unreleased]

### Added
- Scoring engine gained four question types: `order` (exact item sequence),
  `connect` (unordered set of `[source, target, connector]` relationships),
  `hotspot` (set of correct image regions) and `point` (click inside a
  normalized rectangle). `order`/`connect` are JSON-authorable with full
  `load_exam` validation; `hotspot`/`point` carry a binary image and are
  native-only (not exposed to JSON import).
- Native (format-62/63) practice now promotes every native type whose grading
  semantics are established from recovered data:
  - single-blank, case-insensitive fill-in-the-blank (type 8) → `text`;
  - reorder-list (type 5) → `order`, when the stored order is a clean
    permutation of the items;
  - connect (type 7) → `connect`, grading the stored box relationships;
  - point-and-shoot (type 3) → `point` and hotspot (type 9) → `hotspot`,
    whenever a Tk-renderable PNG is recovered from the image field (raw PNG or a
    RichView-wrapped PNG); rects are graded in image-pixel space, so the image
    renders at native size and clicks map 1:1. Records whose image cannot be
    rendered are left unscored rather than promoted blind.
  These join the existing textual single/multiple-choice records (types 0/1).
- Player UI for the new types: a Move up / Move down reordering list for
  `order`, a source/connector/target relationship builder for `connect`, and
  image-canvas widgets for `hotspot` (toggle regions) and `point` (click a spot).
- Result history drill-down: double-click a past result (or select it and choose
  View details) to see its stored breakdown — verdict, score, correct/unanswered
  counts, marked count, mode, elapsed time, passing score and per-section
  results. Surfaces data already persisted by `finish()`; older history rows
  render gracefully with whatever fields they contain.
- Test helpers `plain_list_fixture()`, `fill_question()`, `reorder_question()`,
  `connect_question()`, `hotspot_question()`, `point_question()` and `make_png()`
  build synthetic native containers end-to-end; the Tk smoke test drives the
  reorder, connect, hotspot and point widgets to a scored result.

### Changed
- `native_study.py` refactored into per-type builders (`BUILDERS` dispatch);
  choice promotion behavior is unchanged. The practice-session resume key tag is
  bumped to `native-practice-v3` so earlier choice-only sessions do not resume
  against the broader subset.

### Notes
- Only question shapes the engine can grade faithfully are promoted.
  Drag-and-drop (type 2) and tree (type 4) remain decoded structurally and shown
  in the native view, but deliberately **not** graded: their
  placement/hierarchy-to-answer mapping is not established (see
  docs/ANDROID-QUESTION-SCHEMAS.md), so grading would require a guessed model.
- The image field's exact wrapping is unverified, so `hotspot`/`point` promotion
  is validated on synthetic PNG fixtures only and declines any record whose image
  cannot be recovered and validated.
- No content-key acquisition is performed; the licensed/authenticated key path
  remains out of scope.
