# Benchmark (M5, NFR-6)

Run on 2026-10-09 with `uv run python -m app.benchmark` against the local Ollama host (RTX 4090),
one run per model, models unloaded in between. Input: the synthetic fixture from
`app.benchmark.make_fixture` (10 pages of about 2,700 characters, 10 glossary terms, 3 tables),
DE to EN, 12 segments of at most 3,000 characters, `think=False`, `temperature=0.1`.

| Model | Time | Segments | Glossary hits | Missed | Hit rate | Failed |
|---|---|---|---|---|---|---|
| gemma4:e2b | 92 s | 12 | 369 | 64 | 83% | 0 |
| gemma4:e4b | 65 s | 12 | 369 | 0 | 100% | 0 |
| qwen3:14b | 89 s | 12 | 369 | 0 | 100% | 0 |

## Findings

- **NFR-6 met:** `gemma4:e4b` needs 65 s for 10 pages (target: 300 s).
- **R-1 triggered:** `gemma4:e2b` reaches 83 % (< 90 %), so M8 should label it "draft quality".
  Its misses stay visible in the term report.
- `gemma4:e2b` was slower than `e4b`. Its first run includes a cold model load, and the strict
  retries for missed terms add calls. Treat the "fast" label with care until measured again.
- The fixture is synthetic and term-dense (about 37 hits per page). Real documents will have
  fewer terms; re-measure with the real acceptance document in M9.
- Single run per model, shared GPU: times vary by tens of percent.

## Language consistency on a real document (2026-10-09)

Input: the user's `How The Next Financial Crisis Happens.md` (13 KB, EN→DE, no glossary),
`uv run python -m app.benchmark <models> --file <path> --source en --target de`, local Ollama on
the dev Mac (Apple silicon, shared with other work), one run per model, 3,000 characters per
segment. "Untranslated" counts texts of 40+ characters that `langdetect` still reads as English
after the job; it includes false positives (company-name lines, one German line misread as
English). "Before" is commit `a91aa3c`; "after" is the step-1 fixes (context gate,
segment-level language check, system prompt).

| Model | Code | Time | Calls | Failed blocks | Untranslated |
|---|---|---|---|---|---|
| gemma4:e2b | before | 133 s | 7 | 2 | 5 |
| gemma4:e2b | after | 159 s | 7 | 2 | 5 |
| gemma4:e4b | before | 317 s | 7 | 2 | 4 |
| gemma4:e4b | after | 298 s | 7 | 1 | 2 |
| qwen3:14b | after | 990 s | 7 | 1 | 2 |

- Neither run showed the reported "first 70 % English" cascade; the fixes target its likely
  cause (echo passed on as context), which a fake-LLM test now covers.
- `gemma4:e4b` halves its leftovers with the step-1 fixes; `gemma4:e2b` does not change.
- `qwen3:14b` takes over 16 minutes for about 5 pages on this machine: too slow here for
  interactive use (R-4); times on the RTX 4090 server are in the table above.

### Segment size for `gemma4:e2b` (all fixes, same file)

| Segment size | Time | Segments | Calls | Failed blocks | Untranslated |
|---|---|---|---|---|---|
| 3,000 | 208 s | 5 | 8 | 1 | 5 |
| 1,500 | 161 s | 10 | 12 | 0 | 2 |

Smaller segments make the small model both faster (fewer broken answers and retries of long
segments) and more consistent; the 2 remaining are the false positives named above. The
registry therefore uses 1,500 characters for `gemma4:e2b` and keeps 3,000 for `gemma4:e4b` and
`qwen3:14b` (not measured at other sizes). `SEGMENT_CHARS` overrides all of them.
