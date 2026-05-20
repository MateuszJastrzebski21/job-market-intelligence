# Smoke check (LangChain): ML Engineer (English)

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** en
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
ML Engineer to productionize models from research notebooks into shipped features. Stack: Python, PyTorch, scikit-learn, MLflow, Postgres, Docker. You should be comfortable with feature engineering, cross-validation, hyperparameter search, and serving models behind a REST API. Bonus: experience with text data, embeddings, or competition-grade tabular modelling. We value engineering rigor over raw research output — measurable improvements with reproducible experiments.
```

## Retrieved Chunks (top-5)

### 1. score=0.729  section=approach  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::approach

achievement_id: `3052f2f4-050d-429e-b667-5016aef376ed`  chunk_index: 1

```
[Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Approach]

The dataset is 3+ years of BTC OHLCV data pulled from the Binance
API. Feature engineering produces 30+ technical indicators (momentum,
volatility, volume-derived, trend-following) as model inputs, with
the target being a binary directional label on the next period.

The validation discipline is walk-forward: the time-series is sliced
into expanding (or rolling) train windows with sequential
out-of-sample evaluation, so the model is never evaluated on data
that overlaps with its training in calendar time — the standard
correct setup for any market-data ML problem and the one that
distinguishes a credible thesis from a leak-prone notebook.

The two model families under comparison are XGBoost and LightGBM,
chosen for their strong tabular-data performance and for the fact
that comparing them on this dataset is itself part of the thesis
contribution.
```

### 2. score=0.687  section=approach  chunk_id=data-science-club-pjatk-competitive-admission-active-member::approach

achievement_id: `477e9096-d738-4cbc-acc1-85b8593a7198`  chunk_index: 1

```
[Data Science Club PJATK — Competitive Admission + Active Member — Approach]

Membership is "show up and ship": projects are member-initiated and
team-staffed organically. My contributions during active membership
have spanned three threads.

Competitive ML. Ongoing Numerai tournament submissions with ensemble
ML models — Numerai's setup (anonymized financial features,
encrypted target, walk-forward live evaluation) is a useful proving
ground for tabular modelling without the leak risk that plagues
public-data competitions.

Team hackathons. HackYeah 2025 transport delays tracker (4.3/5 jury
score; see that achievement) was a Data Science Club team entry,
not a solo effort.

Paper implementation. The bus-arrival-punctuality neural network
project (see that achievement) reimplemented an arXiv paper as a
working model with Streamlit visualization — the kind of "read it,
build it, see if it actually works" exercise that the club tends
to produce.
```

### 3. score=0.708  section=lessons  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::lessons

achievement_id: `3052f2f4-050d-429e-b667-5016aef376ed`  chunk_index: 3

```
[Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Lessons]

The clearest lesson was that the validation harness is the
hard part, not the model. Picking XGBoost vs LightGBM is a tuning
exercise; building a walk-forward setup that doesn't accidentally
leak future information through feature scaling, label construction,
or hyperparameter selection is the work that decides whether the
thesis is credible or not. Most public ML-for-trading notebooks fail
this bar.

A second lesson: the gap between "the model beats 50%" and "the model
beats 50% across walk-forward windows with realistic transaction
costs" is enormous. Holding myself to the harder bar is the only way
the result is worth defending.
```

### 4. score=0.705  section=lessons  chunk_id=car-price-prediction-dsc-pjatk-recruitment-competition-7th-of-30-teams::lessons

achievement_id: `4bbbfe8e-dc76-4982-aeba-23ce2588104b`  chunk_index: 3

```
[Car Price Prediction — DSC PJATK Recruitment Competition (7th of 30+ teams) — Lessons]

The biggest lesson was that feature engineering decides the result
more than model choice does. The XGBoost was off-the-shelf; the 100+
binary equipment features and the segmented per-cluster training
were where the leaderboard placement came from. A more sophisticated
model on raw features would have lost to this pipeline.

A second lesson: holding the validation discipline together under
leaderboard pressure is its own skill. The 15 iterative versions
weren't all improvements — some were dead-ends, and the discipline
to revert cleanly when a "smart" change made things worse is the
unsexy half of competitive ML.
```

### 5. score=0.692  section=lessons  chunk_id=data-science-club-pjatk-competitive-admission-active-member::lessons

achievement_id: `477e9096-d738-4cbc-acc1-85b8593a7198`  chunk_index: 3

```
[Data Science Club PJATK — Competitive Admission + Active Member — Lessons]

The clearest lesson was about working in a peer ML group versus
working solo. Solo, you ship what you can hold in your head; in a
group, you ship what survives the group's review of your design
choices, which is consistently a higher bar. The Numerai submissions
in particular have been useful because the group catches modelling
mistakes (subtle leakage, wrong CV split, target distribution
misreads) that solo work would miss until it was too late.

A second lesson: a competitive admission gate is more useful than
it sounds. The selectivity isn't about the membership badge — it's
about ending up in a room where everyone else also passed the same
filter, and the project conversations are correspondingly higher-
signal.
```


## Generated Bullets

- Build a reproducible ML pipeline on 3+ years of BTC OHLCV data with 30+ engineered technical indicators (momentum, volatility, volume, trend) feeding XGBoost vs LightGBM tabular models for binary directional prediction — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Approach]
- Enforce engineering rigor via walk-forward cross-validation with expanding/rolling train windows and sequential out-of-sample evaluation, eliminating temporal leakage through feature scaling, label construction, and hyperparameter selection — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Lessons]
- Place 7th of 30+ teams in the DSC PJATK car-price competition by prioritizing feature engineering (100+ binary equipment features, segmented per-cluster training) over model complexity, with disciplined version control across 15 iterative experiments — [Car Price Prediction — DSC PJATK Recruitment Competition (7th of 30+ teams) — Lessons]
- Submit ongoing ensemble ML models to the Numerai tournament, gaining competition-grade tabular modelling experience on anonymized financial features with walk-forward live evaluation — [Data Science Club PJATK — Competitive Admission + Active Member — Approach]
- Reimplement an arXiv paper as a working bus-arrival-punctuality neural network with Streamlit visualization, demonstrating the "read it, build it, validate it" loop from research to shipped artifact — [Data Science Club PJATK — Competitive Admission + Active Member — Approach]

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/ml-engineer-english.md`:_
