# Licensed installation: findings and compatibility limits

The full Player SHA-256 is
`4a112c2b9cfb2bfc5de39f62ce2739227e878a5f8ebae3289ab9e6d06d96e155`.
Its additional `libcryptvce.dll` SHA-256 is
`27fa008752cdd1feda065377165893ed89cead8356d09d49021b1468dc169f18`.
Evidence and bounded static disassembly are saved in `analysis/licensed/`.
Neither installed binary was changed. This was focused reader/crypto analysis,
not recovery of the complete application source.

Full loader `0x9b9838` calls key loader `0x9b8fb8`; the latter's Delphi cleanup
continuation reads the second pool block and invokes a method callback at
`reader+0x48/+0x4c`, passing the encoded key, file version, and container value.
The callback result governs `ERROR_DECRYPT_EXAM_KEY` or continuation.
See `player-pool-loader.json` and `player-pool-continuation.json`; loader evidence
`ev_b445f976128154cd1ce8b462cc43941b2a18832202f3eef9515979c0c1f74788`.

The full binary includes `DecryptExamKeyRequestVer7`,
`ExecuteDecryptExamKeyRequest`, and a request thread. It contains SQLite cache
SQL with encrypted/decrypted keys, CRC, and date. Lookup method `0xae5fa4`
retrieves a decrypted key for a matching encrypted key. Evidence
`ev_414ae8a7d352201680784853e1940e4c89c19ba20f0d52650430f0ea20894b93`.
These establish an additional application/backend-mediated key path; the exact
network request schema and successful response were not captured.

The DLL exposes certificate-dependent byte transforms and license initialization,
not a direct exported VCE-pool decrypt API. The recovered ABI is documented in
`analysis/licensed/CRYPTO-DLL-FINDINGS.md`. A bounded normal-start observation
recorded the SQLite path but no key-loader execution. The user confirmed the
full installation reaches login and no valid license is held. Authenticated
runtime validation and obtaining the remaining content key could not proceed.
The read-only local schema inspection found no available decrypted-key cache
table. No login or activation checks were changed.

## What is implemented

The reader maps all 206 question envelopes in the supplied format-62 example,
including six groups and nested case studies. It decodes 18 complete content
records with the initial key pool. Earlier observation of 90 decoded identity
blocks must not be described as 90 decoded question bodies. The remaining
12 trailing bytes are uncharacterized.

`native_types.py` preserves field order for every factory-supported native type.
`richview.py` renders the observed text/PNG subset and flags unsupported document
items. `native_view.py` provides the group/question browser; `native_study.py`
adapts only fully decoded textual choices to clearly scoped practice sessions.
Original JSON exams have complete practice/timed playback, results, and sessions.

This is a testable GUI application with partial VCE compatibility. It is not
yet a full replacement for native protected-content playback. Legitimately
available content-key material or an authorized export is still needed for
full decoding and validation; the binaries alone did not provide it.

The original demo documents' conclusions about keyless scrambling and TLS-only
OpenSSL calls are scoped to the captured format-31 sample. Format 62 uses the
separate AES-256-CBC content path recovered during this continuation.
