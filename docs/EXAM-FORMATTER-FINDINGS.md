# Exam Formatter investigation — 2026-10-15

Outcome: **this installed Formatter saves TXT/RTF for Designer to import; the
traced export path does not create a VCE container or expose the protected
exam-key pool. No additional protected questions were decrypted.**

## Target and installed workflow

Target: `C:\Program Files (x86)\Exam Formatter\exam_formatter.exe`, native x86,
1,335,808 bytes, SHA-256
`eead9eabaa702a2ea912e899df5946ca12fdf59f32e1c720fd216ae2cfd1575e`.
REA `open_binary` confirmed the identity. No installed executable was launched
or modified during this investigation.

The installed `readme.txt` labels the tool Exam Formatter v3.0, May 02, 2009.
It describes preparing text imported from PDF for Visual CertExam Designer.
The installed `tutorial.html` makes the two-stage workflow explicit: save the
formatted intermediate document, launch Designer, then use Designer's Save
action to create the VCE file. The tutorial's broad PDF-to-VCE title describes
that combined workflow, rather than direct VCE serialization by Formatter.

## Code-backed save path

Delphi method metadata identifies `aFileSaveAsExecute` at `0x519df0`.
The instruction there calls `0x51a20c`, which configures the save dialog and,
after acceptance, passes the filename to `0x515310` at `0x51a2ad`.

The dispatcher compares extensions with two exact embedded strings:

| Constant | Value | Branch | Worker mode | Output routine |
|---|---|---|---:|---|
| `0x5153a8` | `.txt` | `0x5155e4` | 1 | `0x510918` |
| `0x5153b8` | `.rtf` | `0x515678` | 2 | `0x510b78` |

The branches construct `TExamAsyncRunner`, set its `+0x40` mode byte, and
provide the selected filename at `+0x48`. Its worker at `0x510f68` dispatches
to those two routines.

The text routine assembles question text in a string-list object and writes
that list to the selected file (`0x510a04`–`0x510a0c`). The RTF routine constructs
a RichView object, populates it, and invokes the output method at `0x4b1e74`
from `0x510c32`. Neither traced output branch selects a `.vce` format or invokes
the modern VCE pool-wrapping code found in Designer.

Save-dialog filters at `0x519f1c` and `0x519f5c` independently identify RTF/TXT.
The binary has settings named `LaunchDesignerAfterSaving` and
`DesignerExeLocation`, with the default path
`C:\Program Files\Visual CertExam Suite\designer.exe` at `0x48ab60`.
The ShellExecute import and its caller windows were retained, but this pass
does not claim a runtime-observed Designer launch or a complete proof of every
post-save message-handler branch. The installed tutorial supplies the explicit
handoff workflow.

## Crypto-related observations

The main executable's PE import table lists Windows UI, file/process, shell,
registry, and OLE libraries. Its inventoried imports have no Crypt*/RSA/AES/EVP
entry. The relevant string inventory found no embedded exam-key service or
exam RSA wrapper symbols. This inventory alone would not rule out statically
linked or dynamically resolved crypto; the stronger evidence is the traced
TXT/RTF save dispatch and final writer paths.

The bundled `pdftohtml.exe` and `pdfimages.exe` contain PDF-specific messages
about user/owner passwords, encryption dictionaries, the Standard security
handler, and `EncryptMetadata`. Formatter's command templates invoke those
helpers for PDF import and image extraction. These observations support PDF
protection handling, not VCE pool unwrapping. Their complete cryptographic
implementations were not audited in this pass.

The other bundled image tools do not provide a key lead in the bounded string
inventory. Incidental strings such as a camera `AESetting` property or a GUI
`PasswordChar` property are not treated as evidence of AES or key decryption.

## Relevance to the project

This installation can inform an independent PDF/text import workflow and
RichView/RTF serialization research. It does not provide a new source of the
matching private key or a decoded protected pool for the existing VCE files.
The actual VCE-creation/encryption component in its documented workflow is
Designer, whose RSA public-key wrapping path was already investigated.

The replacement reader, offline exports, and decoded-record counts are
unchanged by this investigation.

## Retained evidence and reproduction

```powershell
python analysis/licensed/inspect_formatter.py
```

- `exam-formatter-inventory.json`: target hash, actual PE imports, output
  constants, worker metadata, relevant strings, companion identities/inventories.
- `formatter-save-references.json`: save-filter and default Designer-path references.
- `formatter-save-windows.json`: Save As entry and dialog initialization.
- `formatter-export-path.json`: dialog acceptance to filename dispatch.
- `formatter-serializer.json`: extension dispatch.
- `formatter-save-branches.json`: TXT/RTF mode setup.
- `formatter-worker.json`: worker mode dispatch.
- `formatter-output-writers.json`: final text/RTF output paths.
- `formatter-shell-thunk.json`, `formatter-launch-callers.json`: shell API linkage.

These assembly artifacts are bounded linear Capstone windows and can include
later code/data. Conclusions above use explicit instruction sequences and
metadata/import links, not an assertion of complete control-flow coverage.
The read-only inventory script's syntax check passed. No GUI/runtime conversion
was performed, and no application source or packaged executable was changed.
