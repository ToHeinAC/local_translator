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
