# Official Android VCE Simulator: first code trace

## Acquired target

Exported from the user's Google Play emulator on 2026-10-16:

- Package: `com.avanset.vcesimulator`.
- Version: `2.6.9`, version code `20609`; min SDK 27, target SDK 36.
- Recorded installer: `com.android.vending`.
- Base APK: 21,856,847 bytes; SHA-256
  `5a9a9d1dee1b76204889f1df5793666e86525bfebd732452481a3e5911fd61ef`.
- Four configuration APKs: English, Dutch, x86_64, xxhdpi.
- Files, individual hashes, and installed-package metadata are in
  `temp/official-vce-android/`. No subscription was purchased or account tokens
  read. Package provenance is recorded; APK signatures were not independently
  cryptographically verified by this analysis.

This is distinct from the original Aptoide APK. The base contains 1,772 ZIP
entries and three DEX files. The x86_64 split contains one native library,
`libsqlcipher.so`; no separate native VCE crypto library was identified there.

## Analysis and coverage

REA archive inspection completed, with no integrity contradictions. Parent
Evidence: `ev_2b23d9b920694f075ef63a218e0f4f55767bbc5d7562aa9b5a8ff5445d197999`.
The summary is retained in `analysis/licensed/official-android-rea-summary.json`.
The archive session was closed after inspection.

Java was decompiled locally with the official JADX 1.5.6 CLI, not with REA's
unconfigured Android provider. Download source:
`https://github.com/skylot/jadx/releases/download/v1.5.6/jadx-1.5.6.zip`.
Its SHA-256 matched the official release asset digest:
`545ea2be9c242511bc145755cf4bda2485ade42966e096f8b4d3da2a230e8974`.

Retained output: `analysis/licensed/official-android-jadx/sources/`.
JADX reported 32 errors and exited with status 1; 29 emitted Java files contain
`JADX ERROR` or `Method not decompiled` markers. This is incomplete
decompilation, not recovered original source. The focused format-62/63 reader
and cipher files below contain neither marker. Their logic is still static
decompiler evidence, not runtime verification or bytecode-level proof.

## Confirmed reader structure

Paths below are relative to the decompiled `sources/defpackage/` directory.
Names may be renamed by JADX to avoid case-insensitive filesystem collisions.

| Version | Format class | Block reader |
|---|---|---|
| 60 | `C2717q20.java` | `C2813r20.java` |
| 61 | `C2991t20.java` | `C3080u20.java` |
| 62 | `C3258w20.java` | `C3346x20.java` |
| 63 | `C3522z20.java` | `A20.java` |

The format classes' `N()` methods return these version numbers, and their
reader factories instantiate the listed classes. Format 62 and 63 admission
also reads the first integer of the last 12 bytes and compares it with file
capacity, corroborating the existing corpus-derived trailer-size observation.

`C3346x20.o()` and `A20.o()` read a framed length, one marker byte, and a
32-bit pool offset, then process `length - 5` ciphertext bytes. They select
the initial pool for marker values below 128 and the separate protected pool
otherwise. If a protected block is encountered before that pool is supplied,
they consume the block and raise an explicit missing-key exception.

Their `L()` methods use `AES/CBC/PKCS5Padding`, take 32 bytes of AES key and
the next 16 bytes of IV at the specified offset, and decrypt the ciphertext.
Java's provider padding name here corresponds to the block padding already
used by the Python decoder. This corroborates the existing modern-format
model; it does not supply the missing protected pool.

## Protected-pool origin

Both readers' `E()` methods pass the Base64-encoded wrapped exam key and key
version to `C0668Sf.a().a(...)`. `C0668Sf.java` builds the service against
`https://www.avanset.com`; `InterfaceC0642Rf.java` declares a form POST to
`/license/v2/index.php?json=true` with fields:

`appid`, `userid`, `userkey`, `ver_app`, `ver_file`, `key`, `ver_key`.

For response `code == 0`, `E()` Base64-decodes `result` and calls `H()`.
`H()` reads a length and then stores that many bytes as the protected pool.
`FA.java` and `AbstractC3557zU.java` show the byte-buffer reader and endian
conversion used for that length.

The traced reader path delegates protected-pool acquisition to the license
service. No local RSA private-key recovery operation was identified in this
path. Generic RSA/public-key strings elsewhere are not evidence of an exam
private key. No requests to the license service were made by these scripts.
Normal Play installation traffic is separate from this static investigation.

## Implication and remaining work

The genuine Android implementation gives a substantially clearer independent
reference for format versions, framing, and question parsing. It corroborates
the current reason protected fields remain unavailable. No additional
protected questions or protected-pool bytes were recovered in this pass.

Remaining work includes detailed question-type/schema comparison, bytecode
corroboration of decompiled control flow where needed, independent APK
signature verification, and resolution of relevant decompilation failures.
The absence of a recovery path in these traced classes does not prove its
absence throughout the entire application or its services.

Reproduce extraction and inventories:

```powershell
python analysis/licensed/extract_official_android.py
python analysis/licensed/inspect_android_apk.py temp/official-vce-android/base.apk --output analysis/licensed/official-android-base-inventory.json
python analysis/licensed/inspect_android_apk.py temp/official-vce-android/split_config.x86_64.apk --output analysis/licensed/official-android-native-inventory.json
```
