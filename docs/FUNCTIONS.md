# Annotated address map (`player.exe`)

Static VAs; image base `0x400000`, no ASLR (VA == runtime address). Roles are
analyst descriptions unless an embedded Delphi name is given. Evidence lives under
`analysis/` (Phase 1), `analysis/phase2/`, `analysis/phase3/`.

## Header & format validation

| VA | Role |
|---|---|
| `0x638F84` | One-byte stream read helper (used by the header validator) |
| `0x949060` | Header validator: require `0x85 0xA8`; `format = b2*10 + b3` → `reader+0x38`; reject `> 63` |
| `0x949FD8` | Loader / format gate: version dispatch; invokes the metadata virtual method |
| `0x949140`, `0x949038` | `INVALID_FILE_FORMAT` message operands (header-failure path) |

## Keystream de-obfuscation (format 31)

| VA | Role |
|---|---|
| `0x63A370` | Length-prefixed string/blob field decoder (seed → le32 length → data) |
| `0x638A2C` | Callback **f** `(((a^b)|1)*(((a+b)&255)^1))&255` |
| `0x638A40` | Callback **g** `(round_half_even(a*sin b) mod 256) ^ c` |
| `0x63A780` | Installs f/g for format 31 into the globals below (refs `0x63A7B6`/`0x63A7AC`) |
| `0xB134D4`, `0xB134CC` | Globals holding the active **f** / **g** pointers (null until a format-31 decode) |
| `0x638E28` | Continues the field keystream to read the `len` data bytes |

## Metadata record — `TVCEFilePropertiesQ`

| VA | Role |
|---|---|
| `0x928F60` | `ReadFromStream` (metadata reader) |
| `0x92BF84` | `WriteToStream` (metadata writer — authoritative encoder, not analyzed) |
| `0x92C598` | `PassDataReading` |
| `0x949D1C` | Metadata virtual method → calls `0x928F60` |

## Record / content model

| VA | Role |
|---|---|
| `0x945274` | Exam-type factory: type0 → `TExamRef` (`[0x94464C]`→VMT `0x9446A4`), type1 → `TCaseStudyExamRef` (`[0x9447D4]`→VMT `0x94482C`); else `UNKNOWN_EXAM_TYPE` |
| `0x949B98` | Record loop: reads typed records, constructs by type, deserializes via VMT `+0xC` |
| `0x9498C0` | Version-dependent payload loader |
| `0x63968C` | Field reader for discriminator `0x15–0x16` |
| `0x8527A0` | Field reader for discriminator `0x3C` |
| `0x852850` | Field reader for discriminator `≥0x3D` (e.g. **format 62**) |

## File-open (add an exam)

| VA | Role |
|---|---|
| `0xADBF24` | `acFileAddExecute` action handler |
| `0xADB7F0` | File-selection workflow; duplicate check → `ALREADY_EXISTS_IN_EXAM_LIST` |
| `0x94BC0C` | Constructs exam reader, runs load, reads metadata, inserts into list |
| `0x949270`, `0x9491A8` | Stream-backed reader construction / init |

## Exam start / run

| VA | Role |
|---|---|
| `0xADCF38` | `acExamStartExecute`; guards on form flags `+0x570`/`+0x57A`, calls `0xADCAB4` |
| `0xADCAB4` | start_impl: validates selection, copies state to main form, calls loader `0xA5D038`, then `0xADFFB4` |
| `0xADCF90` | Case-study guard |
| `0x8055C8` | Resolve selected exam-list entry |
| `0xA5D038` | **Exam loader**: drives the record loop; **load-time integrity gate** → `INVALID_FILE_FORMAT` (refs `0xA5D608`/`0xA5DA90`) |
| `0xADFFB4` | Show / begin exam UI |

## Network / crypto (not file protection)

| VA | Role |
|---|---|
| `ssleay32.dll!0x19011` | Caller of `EVP_CipherInit_ex` (AES-128-GCM) — TLS record layer |
| `libeay32.dll` (various) | Callers of `EVP_DigestInit`/`Update` — OpenSSL/TLS internal |
