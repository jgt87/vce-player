# Runtime validation, evidence, reproduction & tooling gotchas

How the findings were produced and verified, where the evidence is, how to
re-run, and the sharp edges encountered. Read this before continuing the work.

## 1. Toolchain (staged under `.tools/`)

- Ghidra 12.1.4 (`.tools/ghidra_12.1.4_PUBLIC`) + Temurin JDK 21
  (`.tools/jdk-21.0.12.1+1`). Installed by `install-rea-prereqs.ps1`.
- REA (rea-agents MCP) drives Ghidra. It reads `GHIDRA_INSTALL_DIR` and
  `JAVA_HOME` from its process environment — set both to the `.tools` paths.
- Frida venv (`.tools/frida-venv`, frida-tools 17.x, Python 3.12 base).

## 2. Static analysis via REA

REA's native provider needs those env vars. The MCP tools exposed to the agent
did **not** inherit them, so analysis goes through local driver scripts that spawn
REA with the right environment:

- `rea-session.mjs <subdir>` — persistent: connects once (keeps the Ghidra session
  alive across many calls), watches `<subdir>/requests/*.json`, writes each result
  next to it. Good for chained lookups. It aborts the whole run if one request
  file is malformed or one call throws.
- `run-batch.mjs` — one-shot: processes a request dir, catches per-call errors and
  continues, then closes. Good for independent calls.

Request file shape: `{"name":"<tool>","arguments":{…}}`. Tools used:
`open_binary`, `procedure_assembly`, `analyze_function`, `read_bytes`, `xrefs`,
`find_xrefs_to_name`, `procedure_callees`, `search_strings`.

Gotcha — **JSON escaping**: write request files with a real JSON serializer. A
shell heredoc silently turned `C:\\Program` into `C:\Program`, an invalid escape
that crashes the driver on the first parse. (`01-open.json` hit this twice.)

Evidence trees: Phase 1 in `analysis/*.json` (+ `player-evidence.json`,
`player-snapshot.json`), Phase 2 in `analysis/phase2/`, Phase 3 batches in
`analysis/phase3/*.out.json` and `analysis/phase3/reqs2/`. REA results embed an
`evidence_id` and `normalized_result`; parse only the fields you need (dossiers
are up to multiple MB).

## 3. Runtime observation via Frida

`analysis/phase3/frida/`:

- `run.py <seconds> <arg|noarg> <probe.js> [vce_path]` — spawns `player.exe` (as
  the primary instance) under the probe, optionally with a `.vce` path as argv[1],
  records messages to `<probe>.jsonl`, then flushes and kills.
- `attach_run.py <probe.js> <pid> [maxsec]` — attaches to a running Player; stops
  on a `STOP` sentinel file.
- Probes: `probe.js` (broad: header/metadata/decoder/factory/SQLite/OpenSSL),
  `probe2.js` (f/g with correct register args + cipher identity), `probe3.js`
  (plaintext reconstruction from `f`'s EDX arg), `probe4.js` (OpenSSL caller/role).

Gotchas:
- The Player is **single-instance**: launching with a path forwards it to any
  existing instance and exits. Kill stray `player.exe` and spawn fresh so your
  process is primary. (`Get-Process player | Stop-Process -Force`.)
- Opening a path already in `exam_list` shows the cached list without re-decoding.
  To force a fresh metadata decode, open a **renamed copy** of the file.
- The Delphi callbacks use the **register calling convention** (EAX/EDX/ECX).
  Frida's `args[]` reads the stack and returns garbage for them — read
  `this.context.eax/edx/ecx` instead. Return values in EAX are fine via `args`
  `onLeave`.
- **Backgrounded long-running jobs get torn down** by the harness when the next
  tool call runs. Do spawn+instrument+observe inside a single foreground run that
  completes on its own; don't rely on a persistent background Frida/driver.

## 4. REA/Ghidra project instability (important for continuation)

Late in the session, reopening the **cached** Ghidra project started returning
`open_binary` instantly (~110 ms, i.e. reusing the project) but then the REA
server closed the connection on the **first** analysis call ("Connection closed"
/ "Not connected"). Stale `java.exe`/`decompile.exe` from killed batches and/or a
stale project lock are the likely cause.

To recover: kill leftover Ghidra backends (processes whose command line contains
`VCE Player\.tools`: `java.exe`, `decompile.exe`, `demangler_gnu_v2_41.exe`),
remove any `*.lock` under the Ghidra project, and if it still fails, let
`open_binary` re-import and re-analyze from a clean project (~4 min) rather than
reusing the cache. The AES characterization was obtained via Frida instead of
fighting this.

## 5. Validation matrix (what runtime confirmed)

| Claim | Method | Result |
|---|---|---|
| No ASLR; static VAs valid at runtime | module base read | base `0x400000`, delta `0` |
| Header `85 A8`, `format=b2*10+b3`, `>63` reject | asm + runtime hook | confirmed exactly |
| `f`/`g` are the format-31 transforms | runtime globals `[0xB134D4]/[0xB134CC]` after decode | `=0x638A2C`/`0x638A40` |
| `f(a,b)` formula | 14/14 live register samples | exact match |
| `g(a,b,c)` formula | live samples reproduced offline | match (round-half-even, radians) |
| Factory classes | VMT class-name read | type0 `TExamRef`, type1 `TCaseStudyExamRef` |
| Metadata reader on open | `0x928F60` hook | fired; decoded `000-001` / `Exam Sample` |
| Plaintext = `f`'s EDX arg | reconstruct stream | recovered title/number cleanly |
| Questions decode only at start | add-time hooks | record loop/factory/start did NOT fire at add |
| AES-128-GCM role | OpenSSL caller VAs | callers inside `ssleay32`/`libeay32` → TLS, not `.vce` |
| Persistence | live DB read | `exam_list` row carries decoded metadata |

## 6. State hygiene

The instrumented runs added rows to `exam_list`; they were removed afterward,
leaving only the pre-existing row 1. Temporary `.vce` copies were written to the
session scratchpad (not the project) and deleted. No installed file was modified.
