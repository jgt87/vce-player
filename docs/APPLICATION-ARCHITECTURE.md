# Application architecture

Static + runtime findings about how the Player is built and how it runs an exam.
Addresses are static VAs (base `0x400000`, no ASLR).

**Continuation scope note:** the original demo/format-31 findings below must
not be generalized to every version. Format 62 uses AES-256-CBC content blocks;
the full Player has an additional exam-key callback/cache path. See
`LICENSED-PLAYER-FINDINGS.md` and `FORMAT-62-PROGRESS.md`.

## 1. Framework and components

Embarcadero Delphi / VCL, PE32 x86. PE resources contain compiled VCL form
resources, a `PACKAGEINFO` listing `System.*`/`Vcl.*` units, and Delphi published-
method RTTI. Linked libraries: `sqlite3.dll` (local storage), `libeay32.dll` +
`ssleay32.dll` (OpenSSL — used for TLS, see §5).

Class inventory (35 `TVCE*` classes). Domain-relevant ones:

| Class | Role |
|---|---|
| `TVCEFilePropertiesQ` | `.vce` metadata header (see format doc §4) |
| `TVCEStreamProcessorR`, `TVCEReaderR` | stream/decode engine (keystream) |
| `TVCEQuestionSet`, `TVCESection(Collection)`, `TVCETestlet`, `TVCELabCollection` | exam content model |
| `TExamRef`, `TCaseStudyExamRef` | top-level record types (factory `0x945274`) |
| `TVCEHistoryItemC`, `TVCEHistoryManagerC`, `TVCEExamSessionList6` | history/sessions |
| `TVCEExamLaunchOptions` | per-exam launch options (stored as a DB BLOB) |

## 2. File-open path (add an exam)

| Address | Role |
|---|---|
| `0xADBF24` | `acFileAddExecute` action handler |
| `0xADB7F0` | file-selection workflow; duplicate check → `ALREADY_EXISTS_IN_EXAM_LIST` |
| `0x94BC0C` | constructs exam reader, runs load, reads metadata, inserts into list |
| `0x949270` / `0x9491A8` | stream-backed reader construction / init |
| `0x949FD8` | validates format, version dispatch, invokes metadata reader |
| `0x949060` | header signature + format-value check (format doc §2) |
| `0x928F60` | `TVCEFileProperties.ReadFromStream` (metadata) |

Opening a file reads **only** the metadata record (confirmed at runtime: the
record loop and start hooks do not fire at add time).

## 3. Exam start / run chain

Fully mapped (completes the Phase-2 "static-only" items):

```
acExamStartExecute  0xADCF38
  guard: if byte[self+0x570]==0 && byte[self+0x57A]==0 -> call 0xADCAB4(self)
  then byte[self+0x570] = 0
start_impl          0xADCAB4
  r = 0x8055C8(self[0x438])                 # resolve selected list entry
  if r: sel = self[0x56C]
        if sel[0x42] && sel[0x43] && !0xADCF90(self, sel[0x10]): return   # case-study guard
        entry = 0x8055C8(self[0x438])[0x18]
        copy selection state into main form (*0xB0D838): +0x568,+0x56C,+0x5A8,+0x5AC
        ok = 0xA5D038(mainform, entry[0x10], 0)    # <-- exam loader (reads question set)
        if ok: 0xADFFB4(self)                      # show/begin exam UI
```

- **`0xA5D038`** is the exam loader; it drives the record/question reader. It also
  enforces a **load-time validation** that raises `INVALID_FILE_FORMAT`
  (references at `0xA5D608`/`0xA5DA90`): a file can parse at the header+metadata
  level and be added to the list, yet be rejected here on open/start if its full
  content fails the loader's consistency check. See `VCE-FILE-FORMAT.md` §6. (The
  precise rule was deliberately not reverse-engineered — satisfying it for
  arbitrary files is a file-fabrication capability, out of scope.)
- **`0x949B98`** (record loop) reads a sequence of typed records: it reads a count
  via `0x638FD4`, then per record reads a type byte (`0x638F84`), selects a data
  reader by the `self+0x38` discriminator (format doc §5), constructs the subclass
  via factory `0x945274` + VMT `+4` constructor, calls the object's VMT `+0xC`
  (deserialize), writes the loop index to `obj+0x1C`, and conditionally retains
  the object in a collection (`0x4B6578` with `self+0x54`) or releases it. This is
  the question/record deserialization loop.
- **`0x9498C0`** (payload loader) conditionally loads a version-dependent payload
  into an existing object for discriminators `0x28,0x2A–0x2D,0x32–0x36,0x3C–0x3F`
  (requires `self+0x3C` non-null), via `0x7EB0E0` / `0x7ED208` with structured
  cleanup — consistent with loading a text/document payload.

These three (`0xADCF38`, `0x949B98`, `0x9498C0`) were independently disassembled
from the installed binary (`analysis/phase2/missing-methods.md`); their windows
end at Delphi cleanup continuations, so callee semantics beyond the windows are
inferred, not proven. Runtime confirmation needs actually starting an exam (not
done — it was not required for the format/architecture goal and starting it is on
the paid/demo-limited path).

## 4. Local persistence (SQLite)

DB at `C:\ProgramData\VCE Exam Simulator\vcesimulator.db`. Schema read live
(`analysis/phase2/database-schema.json`). Tables: `exam_list`, `exam_sessions`,
`history_items`, `incorrect_questions`, `color_scheme`, `custom_language`,
`demo_prices`, `manager_options`, plus flag tables. Key columns:

- `exam_list(title, file_name, loaded_by_scan, exam_launch_options BLOB,
  training_mode, exam_number, casestudy_mode)` — runtime-confirmed: opening a file
  inserts `title`/`exam_number` decoded from metadata.
- `history_items(…, exam_md5, grade, passing_score, candidate_score,
  incorrect_count, marked_count, incomplete_count, sections BLOB,
  full_exam_info BLOB, …)` — results/scoring.
- `exam_sessions(…, exam_md5, question_index, full_exam_info BLOB, …)` — saved
  in-progress sessions. `exam_md5` keys sessions/history to a specific file.
- `incorrect_questions(candidate_name, exam_md5, incorrect_data BLOB)`.

`vcesimulator.db` is plain SQLite (not encrypted).

### 4.1 BLOB column structures (app config/data, not exam content)

Inspected from the live DB (only two BLOBs were populated; no exam had been taken):

- **`exam_list.exam_launch_options`** (51 B) — **raw, unobfuscated** serialized
  struct: a leading int, an `ff ff` marker, a length/prefixed default candidate
  name string (`"Candidate Name"` in plaintext), then a group of 4-byte integer
  fields (flags/counts, e.g. `0f 00 00 00 01 00 00 00 …`, and `78 00 00 00` = 120,
  plausibly a default time-limit minutes). Not keystreamed.
- **`manager_options.options`** (114 B) — **obfuscated**: a repeating keystream-like
  pattern (`… 6e 6c 6e 68 6e 6c 6e …`) over structured plaintext, i.e. the app's
  manager settings are stored with the same family of byte-level obfuscation as
  `.vce` content rather than in the clear.
- **`exam_sessions.full_exam_info`, `history_items.full_exam_info`/`sections`,
  `incorrect_questions.incorrect_data`** — serialized session/result structures;
  empty in the available DB (no exams taken), so their internal layout is
  undetermined here. By their column semantics they hold a saved exam snapshot,
  per-section results, and the set of incorrectly-answered questions, keyed to a
  file by `exam_md5`.

These are the application's own configuration and result data. The populated ones
contain no exam question content.

## 5. Network / crypto subsystem — AES-128-GCM is TLS, not content protection

Runtime hooking of the OpenSSL exports (caller return addresses captured; no
ASLR) shows the crypto is **entirely inside the bundled OpenSSL DLLs**, not driven
by the Player's own code:

- `EVP_CipherInit_ex` → **AES-128-GCM** (NID 895, key 16, IV 12), called from
  `ssleay32.dll!0x19011` (OpenSSL's TLS/libssl). Exactly two inits per session
  (read + write directions) = the TLS record layer after a handshake.
- `EVP_DigestInit`/`EVP_DigestUpdate` (~24k inits, ~98k updates, 20-byte chunks)
  all called from within `libeay32.dll` (OpenSSL's libcrypto) — TLS PRF / key
  schedule / certificate math / PRNG. Not a file hash.

Conclusion: the OpenSSL AES-128-GCM subsystem is **TLS transport encryption for
the application's network connection** (licensing/activation/promo traffic to
avanset.com — corroborated by the only captured SQL, an `UPDATE demo_prices …
avanset.com/promo/…`). It is **not** part of the `.vce` format and does **not**
protect exam content; `.vce` protection is solely the custom keystream
(`VCE-FILE-FORMAT.md` §3). This resolves the Phase-2 "role unknown" note.

Caveat: the specific endpoint/payload of the network call was not captured (no
application data was seen through the cipher in the short runtime windows — only
handshake-time key setup). Confidence that it is TLS/OpenSSL-internal: high
(callers are inside the OpenSSL DLLs). Confidence on the licensing/promo purpose:
medium-high (inferred from the `demo_prices`/avanset promo URL).

## 6. Security model — file level vs application level

How `.vce` protection and the product's gating actually divide up. The headline:
there is **no strong file-level cryptography**; the meaningful enforcement is
application-level.

| Mechanism | Level | Nature | Strength |
|---|---|---|---|
| Keystream obfuscation (`f`/`g`, `VCE-FILE-FORMAT.md` §3) | File | Content scrambling | **Weak** — *keyless*: the keystream derives from the file's own seed + plaintext feedback. No user/machine/secret key, so a file is self-decoding to anyone with the algorithm. Obfuscation, not encryption. |
| Optional password (`FUsePassword`/`FPassword`) | File | Access flag + value stored in the (keystreamed) metadata | **Weak** — a stored-value check, not a key that encrypts content. |
| Load-time integrity gate (`0xA5D038` → `INVALID_FILE_FORMAT`) | Application | Full-content consistency/format validation on open/start | App-enforced, not cryptographic. Rejects inconsistent/hand-modified files. No keyed MAC/signature was found on the content path (the loader's exact rule was not reversed — out of scope). |
| Licensing / demo limit (5-question cap, `INVALID_REGISTRATION_CODE`) | Application | Playback gating + registration | Entirely app-side; the file is not license-locked. |
| OpenSSL AES-128-GCM | — | TLS network transport (§5) | Strongest crypto in the product, but protects the *connection*, not files. |

Implications:
- **Confidentiality** of `.vce` content rests on the obfuscation algorithm staying
  secret (security-by-obscurity), not on a key.
- **Integrity/authenticity** rests on the application's own load-time checks, not
  on a signature the file carries.
- The strongest cryptography shipped (AES-128-GCM) is spent on the network link,
  not on the exam files.
