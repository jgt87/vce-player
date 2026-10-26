# Protected-pool recovery checks — 2026-10-15

Outcome: **no matching private key or usable offline recovery flaw was found
in this bounded pass. No additional questions were decrypted.**

This continues `PROTECTED-POOL-WRAPPING.md`, checking the two concrete local
possibilities left open there: a packaged matching key and a pool-generation
shortcut. It does not claim exhaustive absence of all possible weaknesses.

## Packaged-key search

`analysis/licensed/audit_matching_keys.py` reads only the 13 EXE/DLL files in
the supplied full and demo installation directories. It searches for PEM
objects and bounded DER private-key structures beginning with a version
integer. It attempts local parsing of those structures and exports only types,
fingerprints, offsets, and public-key match status. No private key bytes are
exported. It also searches for the reference modulus in raw big-endian form.

Results:

- 90 bounded DER private-key candidates were attempted; none parsed as a
  private key matching the exam-wrapping certificate.
- Three PEM certificates parsed: one in each Designer and one in the full
  installation's crypto DLL.
- Both Designers' certificates contain the same RSA public key used by the
  observed exam-pool wrapper.
- The crypto DLL certificate contains a different public key. Its presence
  is not the missing exam-pool private key.
- There are two distinct parsed RSA public keys. Their moduli have no
  nontrivial common factor, and the wrapping modulus is not a perfect square.
- No matching raw modulus sequence was found; the reference certificate is
  stored as Base64 PEM rather than as an unencoded modulus.

The negative result is limited to these encodings and files. It does not rule
out proprietary encodings, encrypted objects, runtime-constructed keys, or
material held only outside the installation. No user credential directories,
process memory, account data, or service endpoints were inspected.

## Embedded crypto DLL object

The previous embedded-object lead at `0x100cbc2c` was followed in the bounded
`0x10004850` assembly window. The decoder passes it to `0x10005d80` at
`0x10004a1b`. The DLL's parseable PEM certificate was inventoried and its
public key differs from the exam wrapper's key. This pass does not equate the
DLL's license-block decoding machinery with RSA unwrapping of exam pools.
The complete semantics of the helper and every proprietary encoded object
remain outside the validated result.

## Randomness/fallback review

The protected generator is `designer.exe!0x8e6d18`, already retained in
`designer-pool-generation.json`. Its relevant instructions are:

```text
0x8e6db6: call 0x8ae4e4   ; actual PE import: RAND_bytes
0x8e6dbb: add esp, 8
0x8e6dbe: mov ebp, eax
0x8e6dc0: dec ebp
0x8e6dc1: jne 0x8e6dd3
...
0x8e6dcc: call 0x40675c   ; copy successful random chunk
0x8e6dd1: add esi, ebx    ; advance populated byte count
0x8e6dd3: cmp esi, 0x800
0x8e6dd9: jl 0x8e6d93
```

Only a return value of 1 takes the copy/advance branch. Failure leaves the
populated-byte count unchanged and the loop retries. Unlike the initial-pool
generator, this reviewed path has no fallback that fills protected bytes with
the application's ordinary random-byte function. The ordinary random used
length is not the protected key bytes themselves.

This is static control-flow evidence, not proof about the entropy available
on the machine that created any exam. OpenSSL's complete RNG implementation,
historical creator versions, external seeding, and possible runtime compromise
were not exhaustively audited. No relationship allowing recovery of protected
RAND_bytes output from the supplied preview bytes was established.

## Practical conclusion and next evidence

The creation algorithm can be described and its expected output framing can
be checked. Those facts do not supply a private exponent or recover the random
pool. The inspected key objects and fallback paths do not currently offer a
working offline unlock.

A matching private key or an already decoded pool from an authorized response
would let the inverse path be validated against these original files. No such
material is presently available. Base64 decoding, changing a license flag,
or knowing the RSA chunk sizes does not replace it.

Reproduce:

```powershell
python analysis/licensed/audit_matching_keys.py
```

Detailed file identities, object metadata, candidate counts, and limitations:
`analysis/licensed/matching-key-audit.json`.
Additional bounded assembly: `analysis/licensed/embedded-license-key-decoder.json`.
Analysis script syntax checks passed. The vendor programs were not launched;
the replacement application and executable were unchanged.
