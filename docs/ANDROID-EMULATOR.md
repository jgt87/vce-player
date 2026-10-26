# Official Android package acquisition

Official publisher page:
https://www.avanset.com/products/vce-exam-simulator-mobile.html

Its Android download links point to:
https://play.google.com/store/apps/details?id=com.avanset.vcesimulator

The official package identifier is `com.avanset.vcesimulator`. The originally
supplied `iseeq-ltd-vce-simulator.apk` is the unrelated `cm.aptoide.pt` client.

Google SDK tools, emulator, and the Android 15 / API 35 Google Play x86_64 image
are installed under `.tools/android-sdk`. SDK command-line tools were downloaded
from Google's repository metadata and verified against its published checksum;
see `analysis/licensed/android-sdk-download.json`. Image and emulator packages
are installed by Google's CLI. Windows acceleration check reports WHPX usable.

Launch the project-local device:

```powershell
./analysis/licensed/start_android_emulator.ps1
```

The launcher creates `VCE_Official_Play` using the Pixel 5 profile, with AVD and
Android configuration under `.tools/android-avd` and `.tools/android-user`.
Runtime logs are in `analysis/licensed/android-runtime`.

Google Play requires interactive user sign-in. Install **VCE Simulator** from
the official listing above. No subscription purchase is necessary to acquire
the free app; its paid functionality remains governed by the publisher.

Once installed, export the APK and all installed splits:

```powershell
python analysis/licensed/extract_official_android.py
```

Outputs go to `temp/official-vce-android`, including SHA-256 hashes and package
metadata. Acquisition provenance does not replace cryptographic signature
verification, which is a separate analysis step.

## REA capability check

The live MCP catalog exposes all ten requested tools: `open_binary`,
`close_binary`, `binary_session`, `list_procedures`, `search_procedures`,
`procedure_pseudo_code`, `list_strings`, `search_strings`, `xrefs`, and
`procedure_references`. `binary_session` also reports the Ghidra 12.1.4 and
JDK 21 native backend available. No target was opened merely to check status.

Android Java decompilation is separate: REA still reports a missing
`REA_JADX_MCP_JAR` provider. Its ADB provider does not inherit the SDK downloaded
here into the already-running server's PATH. Direct project-local ADB commands
remain usable without changing MCP configuration.
