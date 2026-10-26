# Run and validate Study Player

Open `dist/StudyPlayer.exe` after building, or double-click `Launch Player.cmd`
to run the Python source. User data is stored separately in
`%LOCALAPPDATA%/OriginalStudyPlayer/study.db`.

## Functional checks

1. Click **Load example**, then **Start new session**. Answer and mark questions.
2. Use **Previous**, **Next**, and **Review questions**. Use **Check answer** in
   practice mode. Long question text has a scrollable area.
3. **Save & exit**, select the same exam, then **Resume saved session**. Verify
   the answers, position, and review marks are restored.
4. **Finish exam** and inspect the score, section results, and **Result history**.
5. Turn off practice mode before starting a JSON exam to test the countdown.
6. Click **Open VCE** and choose the supplied AZ-104 example. The native viewer
   lists six groups and 206 records, including records that remain encrypted.
7. Select decoded questions to inspect their text/images and stored answer data.
   **Practice decoded textual choices** creates a session limited to reliably
   rendered, decoded choice questions. Its score applies only to that subset.
   Reopen the VCE viewer and use **Resume subset practice** after saving.

The native viewer currently reports 18 fully decoded content records for the
supplied example. A smaller set meets textual-practice rendering checks. The
other records are explicitly unavailable, not silently scored as incorrect.
Native image/tree/link interactions and full protected-content playback remain
incomplete. JSON exams support complete single/multiple-choice and text-answer
sessions. Saved timers pause while the application is closed.

## Automated validation

```powershell
python -m unittest discover -s tests -v
python tests/ui_smoke.py
python player.py --self-test-report validation/source-self-test.json
```

The GUI self-test uses an isolated temporary database. It verifies import,
resource loading, navigation, marking, save/resume, scoring, sections, history,
and timer expiry. `tests/ui_smoke.py` additionally exercises native VCE viewing
and native subset practice with original synthetic fixtures.

## Build the standalone Windows GUI

Dependencies for source native inspection are listed in `requirements.txt`.
The build uses an existing PyInstaller installation:

```powershell
python -m PyInstaller --noconfirm StudyPlayer.spec
dist/StudyPlayer.exe --self-test-report validation/packaged-self-test.json
```

The executable bundles the original example, Python/Tk, and the required reader
dependencies. It excludes installed vendor binaries, user exams, and research
captures. No Python installation is needed to run the resulting executable.
# OEF and VCEX files

Choose **Add exam** (or **Open VCE / VCEX / OEF**) and select the file.
The import notice reports the supported question subset. Select the resulting
library entry, then **Start new session** or **Resume saved session**.
Use **Inspect exam** for the source's readable/encrypted counts.
See [VCEX support and limitations](VCEX-SUPPORT.md).

OEF files from Open Exam Suite support current protobuf and legacy formats.
See [OEF support](OEF-SUPPORT.md) for compatibility and validation.

