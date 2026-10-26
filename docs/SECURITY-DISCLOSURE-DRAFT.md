# Security observation — DRAFT for the vendor (not sent)

A courtesy, high-level security observation about the VCE Exam Simulator, based on
analysis of a locally installed **demo**. This is a draft for the recipient of
this handover to review and decide whether to report to the vendor (Avanset /
Global Simulators Ltd). It contains **no exploit code, no bypass steps, no keys,
and no decoded third-party content** — only a design-level characterization.

## Summary of observations

1. **Exam-file content protection is obfuscation, not encryption.** `.vce` field
   content is scrambled by a self-keyed byte stream whose key material is derived
   from the file's own bytes. There is no secret key (user, machine, or vendor).
   A file is therefore self-decoding to anyone who knows the algorithm — this is
   security-by-obscurity rather than cryptographic confidentiality.

2. **No keyed integrity/authenticity on the content path was observed.** File
   validity appears to be enforced by an application-level consistency check, not
   by a cryptographic signature or MAC tied to a secret. Tamper-evidence that does
   not rely on a secret can, in principle, be reproduced by a modifier.

3. **The strongest cryptography shipped protects the network, not the files.** The
   bundled OpenSSL is used for the application's TLS connection; AES-128-GCM was
   observed only as the TLS record cipher, not for exam-file protection.

## Potential impact (design level)

- Confidentiality of exam content depends on the obfuscation algorithm staying
  secret; it does not survive algorithm disclosure.
- Integrity/authenticity of files rests on application-side checks rather than a
  signature the file carries.

## Constructive suggestions

- If file confidentiality is a goal, use authenticated encryption (an AEAD) with a
  key that is **not** derivable from the file itself.
- For tamper-evidence, add a signature or keyed MAC over the file, verified on
  load, so modified files are cryptographically detectable.

## Scope / ethics

Derived from a legally installed demo for interoperability and security-research
purposes. No third-party or "exam dump" files were decoded in producing this note,
and no circumvention of the product's licensing was performed or is described here.
