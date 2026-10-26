# Protected pool: creation and RSA wrapping

Investigation date: 2026-10-15. **The wrapping algorithm was located; the supplied
protected pools have not been decrypted.**

Follow-up: `PROTECTED-POOL-RECOVERY-CHECKS.md` records the bounded packaged-key
search, public-key comparison, and protected RNG failure-path review. These
checks found no working offline recovery path.

## New target and evidence

The installed Designer is part of the full installation supplied by the user:
`C:\Program Files (x86)\VCE Exam Simulator\designer.exe`, SHA-256
`6d15db70639f084a102222e6e273f4eeb8dbccfe4b1079d3f45d372e4e66e356`.
It contains creation code that is more informative than Player's read path.
No Designer process was launched or license state changed.

REA resource evidence
`ev_ae4b7b62c8700117ab95d6a9a07eb4e35f84efdbb7887248751e05ad1fabd262`
identifies an RCDATA resource named `EXAM_PUBLIC_KEY`, file offset 10800024,
length 2143, SHA-256
`1fc0adf3c2f861ae0a0cd8da952c421cbf880e052d83f947e226a872934d655e`.
The payload parses as an X.509 certificate whose public key is RSA-2048 with
exponent 65537. Certificate SHA-256:
`7d566fa6d33bca4fe02907ac8124cafeaf3ac82f6c778644278fa97c52110112`.
Its subject includes `CN=license.avanset.com` and `O=Global Simulators LTD`.

## Observed creation path

The file writer at `0xb2a584` calls:

1. `0x8e6c70` to generate the initial 1024-byte pool, then copies and serializes it.
2. `0x8e6d18` to generate a 2048-byte protected-pool storage buffer and choose
   a used length in the inclusive range 1024–2048.
3. At `0xb2a665`, writes the used length to a temporary stream, then appends
   the entire 2048-byte storage buffer. The in-memory pool is subsequently
   truncated to the chosen used length (`0xb2a6bd`–`0xb2a6ca`).
4. At `0xb2a6e1`, passes the temporary stream to wrapper `0x8e6e94`.
5. Serializes the wrapped output at `0xb2a6ef`.

Both pool generators call the imported OpenSSL `RAND_bytes` through thunk
`0x8ae4e4`. The initial-pool generator also contains a random-byte fallback
if that call fails. Static presence of that fallback is not evidence that it
executed when any supplied file was created. The protected generator fills its
2048-byte buffer through repeated `RAND_bytes` calls. Its used-length choice
is separate from the key-byte generation.

Wrapper `0x8e6e94` loads an embedded certificate, calls `PEM_read_bio_X509`,
`X509_get_pubkey`, and `EVP_PKEY_get1_RSA`, then feeds the input to
`RSA_public_encrypt`. The actual imports are linked through the PE import table,
not inferred solely from generic RSA symbol strings.

The loop consumes at most 245 (`0xf5`) plaintext bytes per call. Both full and
partial chunks pass padding argument 1. This is the standard RSA PKCS#1 v1.5
encryption layout: with a 2048-bit key, each encrypted chunk occupies 256 bytes.
The input payload has 2052 bytes (four-byte used length plus 2048 storage bytes):

```text
ceil(2052 / 245) = 9 chunks
9 * 256 = 2304 wrapped bytes
```

This provides a code-backed explanation of the second block's size. Earlier
reports treated its possible RSA layout as an unconfirmed size-based hypothesis;
the installed Designer now supplies direct evidence for that creation algorithm.

## Comparison with supplied files

`analysis/licensed/audit_pool_wrapper.py` verifies target/resource hashes,
parses the certificate, and checks every supplied format-62 second block.
All four contain exactly nine full 256-byte chunks. Every chunk interpreted as
a big-endian integer is below the certificate's public modulus, and each file's
nine chunks are distinct. No tested ciphertext/modulus GCD exposed a factor.

These are consistency checks. They do **not** prove the precise certificate
used to create each file, validate decrypted padding, reveal plaintext, or
establish security of every implementation path. No successful unwrap occurred.

## Can it be decoded locally?

The installed creation path performs public-key encryption, not a reversible
mask using the preview pool. The certificate contains the public key needed
to wrap newly generated pools. That public key does not supply the private
exponent needed to unwrap existing ciphertext.

The matching private key has not been identified in the inspected path. The
Player's previously traced credential-bearing service request is consistent
with private-key unwrapping happening outside the client, but the server's
implementation remains unobserved. No claim is made that every packaged byte
or every possible weakness has been exhaustively examined.

The current evidence therefore explains **how the protected pool is wrapped**,
but does not provide an offline method to recover the protected pool in these
files. A decoded pool from an authorized service response or a matching private
key would be required to validate the inverse path against the original exams.

## Reproduction and retained artifacts

```powershell
python analysis/licensed/inventory_key_paths.py
python analysis/licensed/audit_pool_wrapper.py
```

- `key-path-inventory.json`: target hashes, metadata candidates, actual relevant imports.
- `designer-rsa-references.json`: IAT-to-thunk link.
- `designer-rsa-callers.json`: certificate loading and RSA encryption loop.
- `designer-pool-wrap-callers.json`: file-writer call chain.
- `designer-pool-generation.json`: buffer generation, payload preparation, serialization.
- `designer-key-resource-evidence.json`: selected REA resource evidence.
- `designer-resource-snapshot.json`: retained REA resource inventory; session closed.
- `protected-pool-wrapper-audit.json`: certificate metadata and four-file consistency checks.

Assembly artifacts are bounded linear Capstone windows and may include later
code/data; observations above use explicit contiguous instruction sequences.
No application code, executable, or decryption coverage changed in this pass.
The existing optional runtime probe was corrected to reference the protected
slot (`0xb1cbd0`) rather than the initial-pool slot (`0xb1db78`). It was not
executed in this pass. Earlier login-only runs did not capture a pool, and
must not be treated as successful protected-pool observations.
