# IMPROVEMENTS.md

*Analysis date: 2026-07-11*

wordnetify-tinystories is a pipeline that parses the TinyStories corpus into a SQLite database (`wordnetify.py`), then resolves each ambiguous word to a WordNet synset using LLMs — locally via ollama, or remotely via Groq or the OpenAI Batch API (`resolve_multisynsets.py`, `generate_multisynset_batch.py`, `batchcheck.py`, `batchfetch.py`), with a small Flask coordination server (`multisynserver.py`/`multisynclient.py`) for running a cluster. Last substantive commit was 2025-11-28 ("Some kind of documentation thing?"); the tree is clean, and the project appears functional but dormant, with tooling and model choices that have aged.

## Bugs & Fixes

1. **Deprecated/retired model defaults.** `resolve_multisynsets.py` defaults to `llama-3.1-70b-versatile` for Groq — that model was decommissioned by Groq; runs with `--use-groq` and no `--model` will fail today. The ollama default `phi3` is also dated. Make defaults current or fail with a clear message listing valid models.
2. **SQL built by string interpolation.** `resolve_multisynsets.py` builds the main query with f-strings (`story_id % {args.modulo} = {args.congruent}`, the index-creation statements, the pronoun list). Arguments come from argv so injection risk is low, but non-integer input produces confusing SQL errors. Use parameterized queries (`?`) where possible; `argparse type=int` already helps, but the index name interpolation can still produce invalid identifiers for negative values.
3. **Index proliferation.** Each `--congruent/--modulo` combination creates a new partial index (`sentences_by_story_{c}_mod_{m}`) that is never dropped. A 16-way cluster sweep leaves 16 permanent indexes bloating the DB. Create one index on `sentences(story_id, id)` instead.
4. **`nltk.download()` runs on every invocation** at import time in `wordnetify.py` (and `punkt_tab` is listed twice in the README). Guard with `nltk.data.find(...)` try/except, or a `--download-nltk` flag, so offline/cluster runs don't stall on network access.
5. **`read_file_in_chunks` resume position is imprecise**: `file.tell()` is recorded after the `<|endoftext|>` line is read, which is fine, but the final partial chunk is yielded with the same `tell()` semantics — verify resume doesn't duplicate or drop the last story of a file.

## Housekeeping / Modernization (highest-value change)

- **Migrate from requirements.txt to uv.** Delete `requirements.txt`; create `pyproject.toml` and run `uv add nltk tqdm ollama flask requests backoff gunicorn groq openai`, commit `pyproject.toml` + `uv.lock`, and update the README to `uv run wordnetify.py ...` instead of the virtualenv/pip dance. This is the owner's standing preference across all projects.
- The shell wrappers (`groq-runner.sh`, `local-runner.sh`, `openai-runner.sh`) and the `.isc` files (`wordnetify.isc`, `resolve.isc` — apparently isc/cluster job specs) should be documented or removed; `sweep.yaml` references the now-defunct Sweep AI bot and can likely go.
- `.github/workflows/sense-resolution.yaml` and `run-wordnetify.yml` had a churn of revert commits ("Revert openai-runner.sh" x3) — review whether these workflows still run and are wanted; disable or fix.

## Improvements

- **Consolidate the resolver clients.** `resolve_multisynsets.py` (ollama/groq), `generate_multisynset_batch.py` + `batchcheck.py` + `batchfetch.py` (OpenAI batch), and `multisynserver.py`/`multisynclient.py` each duplicate prompt construction, the pronoun exclusion list, and DB access. Extract a shared module (e.g. `wordnet_common.py`) with the prompt builder, exclusion list, and DB helpers.
- **Key handling**: API keys are read from files (`~/.groq.key`, `--openai-api-key` path) — good, no secrets committed. Also honor `GROQ_API_KEY`/`OPENAI_API_KEY` env vars as a fallback so CI and cluster runs are simpler.
- The `resolved_synset` CHECK constraint (`like '%._.__'`) is cryptic; document the expected format in the schema comment.
- Consider Anthropic's Message Batches API as a batch backend alongside OpenAI batch — same 50% cost model, and the three batch scripts already abstract submit/check/fetch.

## Testing

- `tests/` contains only `sample.sql` and `sample.txt` — no actual test code. Add pytest tests for at least: `read_file_in_chunks` (chunk boundaries, resume-from-position, final partial chunk), schema creation idempotence, and the LLM-response parsing in `resolve_multisynsets.py` (this is where malformed model output silently corrupts data). Run with `uv run pytest`.
- Add a tiny end-to-end smoke test: wordnetify `tests/sample.txt` into a temp DB and assert row counts.

## Documentation

- README still documents virtualenv/pip setup — replace with uv instructions.
- README's "Option 1 ... (don't use this)" section is confusing: it tells the reader to install ollama and then not use it. Restructure as "recommended path" (OpenAI batch) vs "alternatives".
- Document the server/client cluster mode (`multisynserver.py` via gunicorn, `multisynclient.py`) — it is completely absent from the README.
- Document `wordpaths.py`, `display_sentence.py`, `make_wordnet_database.py`, and `openaispeed.py` (one line each: what they're for and when to run them).

## Quick Wins

- Fix the duplicated `punkt_tab` line in the README and in `wordnetify.py`'s download calls.
- Add a `.gitignore` entry for `*.sqlite`, `*.sqlite-wal`, `*.sqlite-shm` if not present.
- Amend or squash the vague head commit message ("Some kind of documentation thing?") pattern going forward — commit messages here are often uninformative.
- Pin/refresh model names in the three runner shell scripts to currently available models.
