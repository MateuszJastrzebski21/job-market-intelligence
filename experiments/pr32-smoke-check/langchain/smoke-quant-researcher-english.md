# Smoke check (LangChain): Quant Researcher (English)

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** en
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
Quantitative Researcher position on the systematic equities desk. You will own end-to-end research from data ingestion through model calibration to backtest. Strong Python (pandas, numpy, scipy), comfort with options pricing (Black-Scholes, implied vol surfaces), Monte Carlo methods, and risk-neutral pricing. We value clean experimentation, careful statistical reasoning, and the ability to communicate findings to PMs. PhD nice-to-have, not required.
```

## Retrieved Chunks (top-5)

### 1. score=0.729  section=lessons  chunk_id=implied-volatility-surface-for-spy-options-featured-by-coding-jesus::lessons

achievement_id: `2618ad91-3cda-4411-ac8e-b3c08e23fab6`  chunk_index: 3

```
[Implied Volatility Surface for SPY Options — Featured by Coding Jesus — Lessons]

The biggest lesson was about communicating quantitative work to a
mixed audience. The mathematics of implied volatility — inverting
Black-Scholes, the smile's existence as evidence that the model is
wrong, the term structure as a market expectation — is well-trodden
in textbooks but rarely shown as a thing you can rotate and click.
Building the visualization forced clarity on what was worth showing
(the surface, the rate input, the deformation) versus what was
technical noise (numerical-inversion edge cases, data-cleaning before
inversion).

A secondary lesson: external validation arrives without warning. The
Coding Jesus feature was unsolicited; the project was built for
personal learning and posted to GitHub without outreach. Building
something that clearly communicates substance is the work; signal-
finding takes care of itself when the substance is there.
```

### 2. score=0.698  section=impact  chunk_id=job-market-intelligence-jmi-ai-engineer-portfolio-flagship::impact

achievement_id: `02067d32-9267-408d-8a01-0e9aa41707af`  chunk_index: 2

```
[Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship — Impact]

Concrete state of the project at the time of writing:

- Phase 1 ingestion functional across three sources (HF Jobs API,
  JJIT via extension, NoFluffJobs via extension).
- Phase 2 analytics PoC merged.
- Phase 3 PR-3.1 (data layer for personal-corpus RAG) merged on main.
- Quality bar held: pytest 161 passing, mypy strict 0 errors across
  52 source files, ruff clean, pre-commit 8 hooks passing on every
  commit.
- A dedicated research dossier (5,046 words) drafted for PR-3.2 to
  compare custom RAG against LangChain on this corpus shape, with
  retrieval metrics (recall@k, MRR, nDCG) reported with bootstrap
  confidence intervals.

The project is the most concrete evidence I have that I can build
and operate a typed Python system with senior-level discipline —
ADR-backed decisions, mypy strict, security constraints baked into
the schema, idempotent ingest, all of it.
```

### 3. score=0.736  section=approach  chunk_id=implied-volatility-surface-for-spy-options-featured-by-coding-jesus::approach

achievement_id: `2618ad91-3cda-4411-ac8e-b3c08e23fab6`  chunk_index: 1

```
[Implied Volatility Surface for SPY Options — Featured by Coding Jesus — Approach]

The pipeline pulls SPY option chains from yfinance in real time,
inverts the Black-Scholes formula via SciPy's numerical routines to
recover implied volatilities across the strike-maturity grid, and
renders the result as an interactive 3D surface in Plotly. Streamlit
hosts the UI: users can adjust the risk-free rate input and
immediately see how the surface deforms, making the relationship
between rate assumptions and the smile/term structure visible without
staring at a notebook.

The implementation deliberately exposes the Black-Scholes inversion
rather than hiding it behind a library black box — the choice matters
because the inversion fails (or produces noisy values) for deep OTM
options with thin liquidity, and seeing that breakdown is part of
understanding what implied volatility is and isn't.
```

### 4. score=0.691  section=impact  chunk_id=implied-volatility-surface-for-spy-options-featured-by-coding-jesus::impact

achievement_id: `2618ad91-3cda-4411-ac8e-b3c08e23fab6`  chunk_index: 2

```
[Implied Volatility Surface for SPY Options — Featured by Coding Jesus — Impact]

The Coding Jesus feature is the external signal: an HFT-and-quant
focused audience recommended the project to its 274k subscribers as a
portfolio piece worth replicating. For a self-directed undergraduate
project this is non-trivial validation — it implies the project
communicates quant substance well enough that a domain audience
endorses it publicly.

The live demo at volatilitysurface.streamlit.app remains publicly
accessible. The GitHub repository is referenced in current CV variants
for quant-finance and ML roles.
```

### 5. score=0.751  section=context  chunk_id=implied-volatility-surface-for-spy-options-featured-by-coding-jesus::context

achievement_id: `2618ad91-3cda-4411-ac8e-b3c08e23fab6`  chunk_index: 0

```
[Implied Volatility Surface for SPY Options — Featured by Coding Jesus — Context]

A self-directed quantitative-finance project: constructing a live
implied volatility surface from SPY (S&P 500 ETF) options market data.
The goal was to build an interactive tool that makes the volatility
smile and term structure visible at a glance — both as a personal
learning exercise in options theory and as a public portfolio piece
demonstrating quant chops beyond the typical "trained a model on a
dataset" project.

The project drew unsolicited external attention: it was featured in a
dedicated video by Coding Jesus, a YouTube channel with 274,000
subscribers focused on quantitative finance, HFT, and quant-career
content. The feature video accumulated 26,000+ views and recommended
the project as a quant portfolio piece worth building.
```


## Generated Bullets

- Built an end-to-end implied volatility surface pipeline in Python, ingesting SPY option chains from yfinance and inverting Black-Scholes via SciPy's numerical routines to recover IVs across the strike-maturity grid — [Implied Volatility Surface for SPY Options — Featured by Coding Jesus]
- Deliberately exposed the Black-Scholes inversion rather than hiding it behind a library, surfacing where it breaks down for deep OTM options with thin liquidity — demonstrating careful statistical reasoning about model and data limits — [Implied Volatility Surface for SPY Options — Featured by Coding Jesus]
- Delivered an interactive Plotly/Streamlit tool letting users adjust the risk-free rate input and see the surface deform in real time, making the smile and term structure legible to non-specialists — relevant to communicating quant findings to PMs — [Implied Volatility Surface for SPY Options — Featured by Coding Jesus]
- Earned unsolicited external validation: the project was featured by Coding Jesus (274k subscribers, 26k+ views on the feature) as a quant portfolio piece worth replicating, with the live demo at volatilitysurface.streamlit.app — [Implied Volatility Surface for SPY Options — Featured by Coding Jesus]
- Practiced clean experimentation discipline on a parallel Python research system (JMI): pytest 161 passing, mypy strict 0 errors across 52 files, ruff clean, and retrieval metrics (recall@k, MRR, nDCG) reported with bootstrap confidence intervals — [Job Market Intelligence (JMI) — AI Engineer Portfolio Flagship]

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/quant-researcher-english.md`:_
