# Full Player exam-key request trace

Static investigation, 2026-10-15. Target: the user's installed full Player,
SHA-256 `4a112c2b9cfb2bfc5de39f62ce2739227e878a5f8ebae3289ab9e6d06d96e155`.
The remaining questions have **not** been decrypted.

Follow-up: `RESPONSE-POOL-TRACE.md` resolves the separate-pool marker selection,
Base64 response conversion, and byte-level cache transformation. It supersedes
the unresolved pool-handoff discussion below, while retaining the runtime limits.

## New findings

The previously unresolved reader callback is `0xaeb6c8`. Multiple load sites
explicitly store that address in reader `+0x48` and its receiver in `+0x4c`:
examples include `0x9bb577`, `0x9be178`, and `0xac9a41`.
The callback forwards its arguments to `0xae75a0` at `0xaeb701`.

That routine calls the existing cache lookup `0xae5fa4` at `0xae7634`.
The table's embedded UTF-16 name is `exam_key_cache` at `0xae613c`.
The read-only schema check of the supplied installation's ProgramData database
returned no table containing encrypted/decrypted-key columns. This is a check
of that database only, not proof that no other installation could have a cache.

When a request is needed, `0xae77a7` constructs the class identified by RTTI as
`TDecryptExamKeyRequestThread`. Its fields receive the encoded exam key at
`+0x64`, file version at `+0x50`, and key version at `+0x54`. The thread's Execute
entry `0x99217c` calls `0x991a94` directly.

`0x991a94` builds a request containing these embedded parameter templates:

| Address | Template |
|---|---|
| `0x991f94` | `email=%s` |
| `0x991fb4` | `passwd=%s` |
| `0x991fd4` | `key=%s` |
| `0x992008` | `ver_app=%s` |
| `0x99202c` | `ver_lib=%d` |
| `0x992050` | `ver_file=%s` |
| `0x992074` | `ver_key=%d` |

At `0x991cfa`, the URL argument is the embedded string
`https://www.avanset.com/license/v2/index.php`; the request call is at
`0x991d02`. Returned text is parsed, with a status stored in thread `+0x58`
at `0x991dd5` and another response field stored in `+0x60` at `0x991e71`.
The caller's success path converts response data into a stream, and for file
versions >=52 reads a four-byte length followed by that many bytes
(`0xae7a56` through `0xae7ac4`). Cache insert/update calls follow.

This connects the encoded block to a credential-bearing service request and
response processing. It supports the service-backed key interpretation more
strongly than the earlier isolated request-name strings did.

## What this establishes and what remains open

The field cipher remains AES-256-CBC with a key/IV selected from a pool.
This trace explains how the full Player requests additional key data. It does
not reveal the service's private implementation, produce the response, or
establish an offline way to derive the missing content pool from this file.
No service requests were sent and no account credentials were read.

The response stream and the initial/final pool globals use different global
slots. Their entire downstream object-lifetime/handoff path has not been
independently resolved in this pass; do not equate their addresses merely
because they participate in the same request flow.

The RSA symbol reference found in this bounded scan is a symbol-registration
candidate, not evidence that RSA locally unwraps this exam's second block.
No successful local unwrap was found. This investigation cannot prove that
every possible offline route is absent.

## Reproducible evidence

- `analysis/licensed/find_key_references.py` and `key-reference-candidates.json`:
  raw reference candidates, embedded request strings, binary digest.
- `analysis/licensed/key-callback-windows.json`: callback forwarding, cache
  branch, request construction, response and cache handling.
- `analysis/licensed/key-request-implementation.json`: request construction
  and response parsing at `0x991a94`.
- `analysis/licensed/key-request-dispatch.json`: Execute at `0x99217c`.
- `analysis/licensed/player-pool-continuation.json`: original encoded-block
  callback invocation at `0x9b90e2`.

These are bounded, linear Capstone windows; they can include subsequent
routines and data. Code claims above use explicit contiguous instruction
sequences and linked call targets. They are static evidence, not successful
runtime observation. The replacement GUI and its decoding coverage are unchanged.
