# Diagrams

ASCII diagrams of the `.vce` layout and the player's control flow. Addresses are
static VAs (base `0x400000`, no ASLR). See `FUNCTIONS.md` for the full map.

## `.vce` container layout (format 31, validated)

```
+--------+------------------------------------------------------------+
| off 0  | 0x85 0xA8            signature                             |
| off 2  | b2 b3               version bytes -> format = b2*10 + b3    |  header (plaintext)
+--------+------------------------------------------------------------+
| off 4  | 0x00                leading byte consumed before fields    |
+--------+------------------------------------------------------------+
| off 5  | STRING FExamNumber  seed(1) | E(le32 len | ansi[len])      |  metadata record
|  ...   | STRING FExamTitle   seed(1) | E(le32 len | ansi[len])      |  (TVCEFilePropertiesQ)
|  ...   | ... more string fields ...                                 |
|  ...   | 2x 4-byte integer fields                                   |  low-entropy region
|  ...   | 4x 8-byte timestamp fields (Created/Modified Unix)         |  (encoding not fully
|  ...   | 7x 1-byte flag/small fields (ShowDescription, UsePassword) |   pinned down)
+--------+------------------------------------------------------------+
| ...    | question/record blocks: read in bulk after metadata        |  content (keystreamed);
|        | TExamRef / TCaseStudyExamRef, sections, questions          |  validated by the loader
+--------+------------------------------------------------------------+

E(...) = per-field keystream: seed -> k0 = g(0x80, f(seed, seed^0x80), 0);
         per byte  p = c ^ k ;  k = g(k, f(c,p), (i&0xff)+1)      (one stream per field)
```

## Keystream (per field)

```
 seed ---> k0 = g(0x80, f(seed, seed^0x80), 0)
   |
   v   for each ciphertext byte c (i = 0,1,2,...):
        p_i = c_i XOR k_{i-1}                 <- decoded plaintext byte
        k_i = g(k_{i-1}, f(c_i, p_i), (i & 0xff) + 1)

 f(a,b) = (((a^b)|1) * (((a+b)&255)^1)) & 255
 g(a,b,c) = (round_half_even(a*sin(b)) mod 256) ^ c       (b in radians)
```

## Open (add exam)  vs  Start (run exam)

```
ADD (File > Add)                           START (open/begin an exam)
  acFileAddExecute 0xADBF24                   acExamStartExecute 0xADCF38
      |                                           |  (guards +0x570/+0x57A)
      v                                           v
  file-select 0xADB7F0                        start_impl 0xADCAB4
      |                                           |  resolve selection 0x8055C8
      v                                           |  copy state -> main form
  build reader + load 0x94BC0C                    v
      |                                        exam loader 0xA5D038  --(fail)--> INVALID_FILE_FORMAT
      v                                           |                               (integrity gate
  format gate 0x949FD8                            |                                0xA5D608/0xA5DA90)
      |  header 0x949060 (85 A8, ver)             v
      v                                        record loop 0x949B98
  metadata reader 0x928F60                        |  factory 0x945274 -> TExamRef / TCaseStudyExamRef
      |  decode FExamNumber / FExamTitle          |  deserialize via VMT +0xC
      v                                           v
  INSERT into exam_list (title, number)        0xADFFB4 show / begin exam UI

Note: ADD reads only header+metadata (confirmed). Question content decodes at START.
```
