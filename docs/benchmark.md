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

## Legal texts, both directions (2026-10-10)

Input: two statutes from the knowledge base `KB_BS_local-hybrid-researcher/kb/StrlSch__db_inserted/`:
`AtG.pdf` (German original, 722 blocks, 186,000 characters, about 70 pages) DE→EN, and
`strlschg_en_bf.pdf` (BfS English translation of the StrlSchG, 2,715 blocks, 465,000 characters,
about 170 pages) EN→DE. Local Ollama on the RTX 4090 host, one run per model, models unloaded in
between, each model at its registry segment size (e2b 1,500, others 3,000 characters):

```
uv run python -m app.benchmark <model> --file <pdf> --source de --target en \
  --glossary atg_de_en.csv --segment-chars <n> --out data/bench
```

Glossaries (terms taken from the texts; StrlSchG terms from the BfS translation; terms that
often start German compounds, such as "emergency" → "Notfall…", were left out because the
check would count correct compounds as misses):

- AtG DE→EN (11): Kernbrennstoff, Genehmigung (licence), Aufsichtsbehörde, Endlager
  (repository), Zwischenlager (interim storage facility), Kernkraftwerk, Stilllegung,
  Deckungsvorsorge (financial security), Schadensersatz (compensation), Sicherheitsüberprüfung
  (safety review), Strahlenschutz.
- StrlSchG EN→DE (10): radiation protection executive (Strahlenschutzverantwortliche),
  radiation protection supervisor (Strahlenschutzbeauftragte), radiation protection register,
  exposure situation, reference level, dose constraint (Dosisrichtwert), controlled area,
  supervised area, clearance (Freigabe), contamination.

| Document | Model | Time | Segments | Calls | Glossary hits | Missed | Hit rate | Failed | Untranslated |
|---|---|---|---|---|---|---|---|---|---|
| AtG DE→EN | gemma4:e2b | 186 s | 151 | 173 | 298 | 22 | 93% | 0 | 0 |
| AtG DE→EN | gemma4:e4b | 308 s | 70 | 89 | 294 | 19 | 94% | 0 | 0 |
| AtG DE→EN | qwen3:14b | 654 s | 70 | 92 | 294 | 21 | 93% | 2 | 3 |
| StrlSchG EN→DE | gemma4:e2b | 597 s | 352 | 516 | 337 | 11 | 97% | 33 | 35 |
| StrlSchG EN→DE | gemma4:e4b | 1,038 s | 165 | 289 | 337 | 18 | 95% | 3 | 2 |
| StrlSchG EN→DE | qwen3:14b | 3,782 s | 165 | 223 | 337 | 23 | 93% | 35 | 14 |

### Findings

- **`gemma4:e4b` is the best default here:** few failures in both directions, about 14 pages
  per minute DE→EN and 10 pages per minute EN→DE. But it has the tag leak below.
- **`gemma4:e2b`** is fine DE→EN (fastest, nothing failed), but EN→DE it left about 35 blocks
  in English, in runs of neighbouring blocks (whole segments, for example definitions (10) to
  (12) of section 5 and list items 12 to 16), and needed 516 calls for 352 segments.
- **`qwen3:14b`** gives the best wording (for example "das gewichtete Mittel" for "weighted
  average", where e4b writes "das gewichtete Durchschnitt" and "Landesverordnung" for
  "statutory ordinance"), but it is 2 to 3.6 times slower than e4b and failed on 35 StrlSchG
  blocks, among them a run of 17 neighbouring blocks (sections 167 to 169) left in English. Why that stretch failed and
  why the run took 63 minutes was not checked (no Ollama request log on this host).
- **Tag leak (`gemma4:e4b` only):** it wraps words in `<b>…</b>` (copied literally, ellipsis
  included) or `<a1>…</a1>`, mostly around glossary terms: 44 of 722 AtG blocks and 154 of
  2,715 StrlSchG blocks. The tags come from the rule "Keep tags such as <b>…</b> …" that
  `prompt.py` sends with every request, also for PDF/MD input that has no tags. They end up
  verbatim in the MD and PDF output. Neither e2b nor qwen3 does this.
- **Glossary misses are mostly counting artefacts:** "supervisory authorities" is not seen as
  "supervisory authority" (the suffix rule has no "-ies"). Real misses are near-synonyms, such
  as "interim storage" for "interim storage facility". The rate is 93 to 97 % for all models.
- **Legal style:** all models render "Section 70" as "Abschnitt 70", not "§ 70". The PDF
  reader found no headings in the StrlSchG PDF (all 2,715 blocks are paragraphs).
