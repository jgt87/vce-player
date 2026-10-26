# Supplied Android APK: identity and investigation boundary

The supplied `temp/iseeq-ltd-vce-simulator.apk` contains the **Aptoide app-store
client**, not the VCE Simulator application package.

Source SHA-256:
`188bbdb899be2da401ac0471ba4d10693612fa1067f2ea0987cc6e1afcfd4374`.
Size: 20,072,145 bytes. No APK was installed or executed.

## Direct evidence

The decoded binary Android manifest declares:

| Field | Value |
|---|---|
| Package | `cm.aptoide.pt` |
| Version name | `9.22.5.3` |
| Version code | `12060` |
| Application class | `cm.aptoide.pt.NotificationApplicationView` |
| Main activity | `cm.aptoide.pt.view.MainActivity` |
| Minimum / target SDK | 16 / 32 |

ZIP inventory contains three DEX files and no nested `.apk` entry. The eight
native libraries are Sentry diagnostic libraries for four CPU architectures;
no VCE reader or `libcryptvce` native library was identified. DEX metadata
contains Aptoide app-store classes, including its home/editor-choice and
installation infrastructure. The targeted class-descriptor inventory found no
Avanset/ISEEQ/VCE app types.

AES/RSA/Cipher strings occur in advertising, generic crypto, networking, and
other bundled library metadata. String presence does not tie them to VCE file
decryption. No VCE exam-key endpoint or exam-pool implementation was identified
in this package. The filename alone does not establish the package identity.

## REA use and limitation

REA `open_binary` identified the supplied file as an APK archive with the hash
above. `inspect_artifact` completed the archive inventory (4089 contained
entries, plus the root occurrence; no reported integrity contradictions).
Its summary is retained in `analysis/licensed/android-archive-rea-summary.json`.
REA parent inspection Evidence:
`ev_3ab7b4732ab0d082593fddbd3046f7ec5cd6fd87d3b547a123b19b56ca4baabf`.

The separate REA Android-decompiler call returned `capability_unavailable`:
`REA_JADX_MCP_JAR` is not configured for the required caller-supplied
jadx-headless-mcp 0.7.1 JAR. No configuration was changed and no engine was
downloaded. That prevents Java control-flow decompilation through this provider,
but does not prevent reading the APK's binary manifest or DEX metadata directly.

The manifest and DEX observations above are from the retained local Python
parsers, not represented as successful REA JADX output. They establish the
package identity without executing it. Signatures were not verified.

The archive session was closed. Archive snapshot saving was unsupported
because that route has no concrete native analysis profile; the successful
REA summary and local inventory remain on disk.

## Next useful input

### Follow-up bootstrap audit

`analysis/licensed/inspect_android_bootstrap.py` additionally inspected every
ZIP member for ASCII/UTF-16 target strings, all three DEX string tables,
all eleven assets, declared manifest routing, the ZIP comment, and the APK
signing-block envelope. Results are retained in
`analysis/licensed/android-bootstrap-audit.json`.

- `assets/down.json` is a Lottie animation named `Thumbs-down`, not a download
  manifest. The other reaction JSON files and logo assets are app-store UI.
- `assets/filedownloader.properties` configures generic downloader behavior;
  no VCE-specific destination was found.
- Manifest routes include `aptoide`, `aptoideinstall`, `aptoidesearch`, market,
  and Aptoide web links. No explicit VCE target was found in these declarations.
- 130 URL string occurrences were retained, including generic Aptoide service,
  advertising, analytics, and library URLs. No VCE-specific URL was identified.
- Broad target-string matches were incidental: `elementWiseEquals`, image
  Base64, and signature digest text. They are not VCE code or configuration.
- The ZIP comment is empty. A 12,288-byte signing block begins at offset
  19,819,730. Its pair IDs are `0x7109871a` (803 payload bytes), `0x504b4453`
  (11,161 bytes), and `0x42726577` (256 zero bytes). No target ASCII strings
  were found in these payloads. The opaque payload was inventoried, not decoded;
  signatures were not verified.

This follow-up found no embedded VCE APK or explicit VCE download target.
Static searches cannot exclude computed, encoded, or remotely supplied targets.
It adds no recovered VCE decryption material. The actual VCE application APK
remains necessary to investigate its reader implementation.

Reproduce: `python analysis/licensed/inspect_android_bootstrap.py`.

To inspect VCE Simulator's Android file reader, the actual installed VCE
Simulator APK (and any required split APKs) is needed. The Aptoide client may
download another package at runtime, but this pass did not execute it or fetch
another APK. No substitute target was selected.

Reproduce local inspection:

```powershell
python analysis/licensed/inspect_android_apk.py
python analysis/licensed/read_apk_manifest.py
```

Retained output: `android-apk-inventory.json` and
`android-manifest-declarations.json` under `analysis/licensed/`.
