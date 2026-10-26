# Study Player validation

Build: `dist/StudyPlayer.exe`, standalone Windows GUI, 16.7 MB approximately.
SHA-256: `b8bb4e5478c625ac27f554567a923f285d086fc6399570b92d85b5f09f84ba2b`.

| Check | Result |
|---|---|
| Unit/integration suite | 32 tests passed |
| Tk GUI workflow smoke | Passed: JSON import, navigation, marking, save/resume, scores, timer, history, native viewer, subset save/resume |
| Source GUI self-test | Passed; `source-self-test.json` |
| Packaged executable self-test | Passed; `packaged-self-test.json` |
| Supplied AZ-104 file framing | 206 records, six groups, 12 uncharacterized trailing bytes |
| Supplied file complete content decoding | 18 records |
| Supplied file conservative practice subset | 4 textual choices, after document/context validation |
| Visible-window manual/automated review | Not completed: computer-use app approval timed out |

The executable self-test uses a temporary isolated database, the bundled original
JSON example, and original synthetic native content. It exercises real Tk widgets
without needing a vendor account. No vendor binaries, license data, or supplied
exam question content are bundled into the executable.

The count of four practice questions is intentionally smaller than 18 decoded
records: unsupported interaction types, document items, images, or incomplete
case-study context are excluded from scoring. Native protected-content playback
for the complete 206-question file is not validated or claimed.

Reproduce the packaged checks:

```powershell
dist/StudyPlayer.exe --self-test-report validation/packaged-self-test.json
```

For interactive checking, open the executable and follow
`docs/RUNNING-THE-APP.md`. The viewer exposes encrypted and unsupported records
so a failed decoding path is visible during testing.
