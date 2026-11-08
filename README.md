# Promo Finder — Kuku AI Generalist assignment, Problem 1

Reads timed microdrama screenplays and returns ranked **20–60 s promo clips**, each with:
- episode and start/end timestamps for every segment
- the hook (first 3 s) and the cliffhanger
- one line on why it works
- a "post these first" slate

## Run it (about 1 minute, no API key needed)
```bash
python -m promo_finder.cli --input path/to/show.zip --out raw_outputs/rules_only      # folder or .zip
python tests/test_pipeline.py                                                          # synthetic tests
```
Optional LLM judge. The model is set by one flag and called over plain HTTP (no SDKs):
```bash
GEMINI_API_KEY=... python -m promo_finder.cli --input show.zip --out raw_outputs/gemini --provider gemini
GROQ_API_KEY=...   python -m promo_finder.cli --input show.zip --out raw_outputs/groq   --provider groq
# any OpenAI-compatible endpoint (e.g. a model API Kuku provides):
LLM_API_KEY=... python -m promo_finder.cli --input show.zip --provider openai --base-url https://host/v1 --model NAME
# anthropic | ollama (local) | openrouter | mock (offline test)
```
UI: `pip install -r requirements.txt && streamlit run app.py`. Colab: open `promo_finder_colab.ipynb`.

## How it works
| Stage | Who | What |
|---|---|---|
| 1. Parse + audit | code | screenplay → typed events (camera / action / sfx / dialogue + delivery tags); format checks |
| 2. Legal cuts | code | cut points = camera-shot boundaries that are not inside a spoken line or a "…"-split sentence |
| 3. Score every window | rules | hook (first 3 s) · cliffhanger (last 4.5 s, cut-before-answer bonus, ends-on-answer penalty) · body intensity · standalone (backstory words, cast size) |
| 4. Shortlist | code | 20–60 s continuous windows + 2-segment stitches → non-overlap filter → at most 3 per episode |
| 5. Judge (optional) | LLM | re-scores the top 40; may move cuts **by line ID only**; code snaps them to legal cuts and checks 20–60 s |
| 6. Rank | code | quality × funnel position (earlier episodes are favoured: fewer spoilers, viewers land at ep 1) with diversity rules |

## Outputs (`raw_outputs/<run>/`)
`promos_report.md` (human-readable, with clip transcripts) · `promos.csv` · `promos.json` · `review_sheet.csv`
(blank columns for editor labels) · `evaluation.json` · `data_quality.json`

## Layout
`promo_finder/` parser · audit · signals (lexicons) · candidates · llm (providers) · judge · report · evaluate · cli
`quality/manual_review_top20.md` · `tests/` · `app.py` · `promo_finder_colab.ipynb`

The input pack is confidential: `.gitignore` excludes `data/` and `*.zip`. Do not commit screenplays.
