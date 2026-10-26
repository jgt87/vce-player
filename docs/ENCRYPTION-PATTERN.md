# Supplied AZ-104 file: encryption and question-6 failure

The file SHA-256 remains
`9185153df517ab6fb97efdb5aa795ce4976db713ee59c9c3aecb5933c924c513`.
The audit checks every record's identity, prompt, and answer independently;
failure to decode an identity does not prevent checking the following fields.
It exports framing/status only, not question content or key bytes.

## Established pattern

The format-62 native reader uses the same block algorithm for working and
failing questions:

1. Decode a five-byte seeded length header using the recovered byte callbacks.
2. Read the marker byte: values below 128 select the initial pool; values
   at or above 128 select the separate protected content pool.
3. For a nonempty encrypted field, read a little-endian 32-bit key-pool offset.
4. Read `decoded_length - 5` ciphertext bytes, in 16-byte AES blocks.
5. Select a 32-byte AES key and the following 16-byte IV from the indicated pool.
6. Decrypt AES-256-CBC and remove PKCS#7 padding.
7. Parse the decrypted document/answer according to its record type.

The initial pool is 1024 bytes at file offset 13. A second 2304-byte encoded
key block follows. The full Player passes that block to its separate exam-key
callback, with a cache/request path described in `LICENSED-PLAYER-FINDINGS.md`.
The skipped second block has not been recovered as a usable full content pool.
The installed Designer's creation code now explains its 2304-byte size as
nine RSA-2048 encrypted chunks; see `PROTECTED-POOL-WRAPPING.md`. This is
wrapping-algorithm evidence, not successful recovery of the pool.

## Exact boundary evidence

| Field | Question 5 | Question 6 |
|---|---|---|
| Record file offset | 13835 | 16668 |
| Identity key-pool offset | 63, decrypts | 1707, outside the 1024-byte pool |
| Prompt key-pool offset | 439, decrypts and parses as RichView | 969, fits but decryption/padding fails |
| Answer key-pool offset | 222, decrypts | 882, fits but decryption/padding fails |

The identity of question 6 would require bytes 1707 through 1754 inclusive.
The prompt/answer failures demonstrate that simply extending the initial pool
with zeroes would not supply the correct key bytes already referenced within
its existing range.

## Audit result and limits

All 206 envelopes were checked. The earlier diagnostic tried the initial pool
for every field and reported 57 padding successes. The corrected marker-aware
audit identifies 54 initial-pool fields and 564 protected-pool fields. The three
extra padding successes were not valid recovered content. All 54 initial-pool
fields decrypt successfully; the protected pool is unavailable. There are still
18 complete decoded records and no additional recovered questions.

The algorithm is established, but the additional content-key material is still
missing. The full installation reached login and the user confirmed no valid
license is available, so its normal authenticated key path could not be tested
successfully. Static analysis has not established a local derivation that
recovers that material. It would be incorrect to claim the remainder is decoded
or to treat the AES key as an inferable repeating-byte mask.

Reproduce the audit:

```powershell
python analysis/compatibility/audit_encryption.py "temp/Microsoft.actualtests.AZ-104.v2026-08-12.by.ida.206q.vce"
```

Detailed per-record offsets and status are in
`analysis/compatibility/encryption-audit.json`. The GUI executable was not
changed by this diagnostic investigation.

## Follow-up: resolved exam-key callback

The full Player's callback has now been connected to a cache lookup and an
exam-key request thread. That thread sends the encoded key, version fields,
and account credentials to the embedded Avanset license endpoint and parses
response key data. See `KEY-REQUEST-TRACE.md` for addresses, evidence, and limits.
No additional questions were decrypted; the missing key material remains
unavailable in the supplied unauthenticated installation.
