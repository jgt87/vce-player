# Format-62 compatibility investigation

**Later implementation:** the GUI now maps all 206 record envelopes, decodes
18 complete content records, and offers four conservative textual practice
questions for the supplied example. Other protected content remains unavailable.
See `LICENSED-PLAYER-FINDINGS.md`, `RUNNING-THE-APP.md`, and
`../validation/VALIDATION.md`. The investigation log below records intermediate
findings; its earlier metadata-only implementation status has been superseded.

The original docs principally describe the bundled format-31 sample. The user's
example has header `85 A8 06 02`, format value 62, size 6,809,328 bytes, SHA-256
`9185153df517ab6fb97efdb5aa795ce4976db713ee59c9c3aecb5933c924c513`.
Its identity is recorded in `analysis/compatibility/target-identity.json`.

## Recovered and validated

- Version dispatch and metadata field order reuse the saved assembly in
  `analysis/30-metadata-assembly-rest.json`, especially `0x92aaa2` onward.
- `0x852850` constructs a text stream and delegates to `0x8528b8`.
  REA evidence `ev_6cfc3b38bb9d89432185debba311dc4f9d36b9c27ff0363a67a60f5db55e1655`.
- Length reader `0x851e24` decodes a seed and four little-endian bytes through
  callbacks initialized at `0xaf83b4`: `f(a,b)=a XOR b`,
  `g(a,b,c)=((a+b) AND 255) OR c`. The initial key byte is zero.
  Evidence `ev_b5ec2ba158043be2bfc353b29e5c32c77db4aaba95c8dc7ff953da9e2fafdfec`.
- `0x8528b8` subtracts five from the decoded block length, consumes a marker,
  and reads a key-pool offset followed by ciphertext when the remainder is
  positive. Evidence `ev_f0138329b8526bf76b1a72eac8cd135fdbe41c51f263cfe4efc77172188d3007`.
- `0x852610` calls EVP AES-256-CBC decrypt functions. Its key is 32 bytes and
  IV is the following 16 bytes from the key pool, selected by the stored offset.
  Evidence `ev_af0aa8f8a2f40ee809746b7ff9005e3ea471bd4cb300c122af0e00549c656ba4`;
  import names are captured in `analysis/compatibility/reader-evidence.json`.
- The example's initial key pool is 1024 bytes at offset 13. A following
  2304-byte reserved block is skipped by `0x852160` (called in the cleanup
  continuation after `0x949828`), placing metadata at offset 3346.
- The bounded runtime observation in `analysis/phase3/frida/probe62.jsonl`
  observed pool length 1024, skipped length 2304, metadata format 62, and the
  strings `AZ-104`, `AZ-104`, `1`. Offline `vce_reader.read_metadata` reproduces
  these. The following integers are raw passing score 800 and time limit 120.
  Two observed timestamp values are 1595412946 and 1644317301. Passing-score
  scaling is not assumed to equal the JSON player's percentage rules.

## Corrections to earlier scope assumptions

The earlier observation that AES-128-GCM belongs to TLS is still valid for those
captured calls. It does **not** establish that all VCE versions lack content
encryption: format-62 metadata uses the separate AES-256-CBC path above. Likewise,
the sample's format-31 string codec cannot be applied to the newer container.

The metadata parser is implemented in `vce_reader.py` and exposed through the
VCE inspector. It reads a bounded prefix and checks lengths, key offsets,
cipher-block size, padding, and UTF-8. It is not a complete question reader.

## Remaining work

Recover index/reference layout, key-pool changes during full exam loading,
per-question-type serializers, section/case-study relationships, and RichView
document text/image structure. Header/metadata success does not demonstrate
full-file consistency or exam playback compatibility. No license gating is
modified. The observation launched and closed its own demo process; opening
the file may have created an entry in the vendor's exam list.
