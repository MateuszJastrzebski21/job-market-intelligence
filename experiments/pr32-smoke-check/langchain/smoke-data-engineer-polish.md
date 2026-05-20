# Smoke check (LangChain): Data Engineer (Polish)

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** pl
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
Data Engineer — projektowanie i utrzymanie pipeline'ów danych w środowisku produkcyjnym. Stack: Python, SQL (PostgreSQL), Airflow lub podobny orchestrator, batch processing (Spark/Pandas), Docker. Oczekujemy doświadczenia w pracy z dużymi wolumenami danych, monitoringu jakości danych oraz w pisaniu czystego kodu z testami. Mile widziane: praca z systemami wielowątkowymi, doświadczenie z obciążeniem produkcyjnym oraz znajomość praktyk dobrego inżynierowania.
```

## Retrieved Chunks (top-5)

### 1. score=0.671  section=approach  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::approach

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

### 2. score=0.671  section=impact  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::impact

achievement_id: `3052f2f4-050d-429e-b667-5016aef376ed`  chunk_index: 2

```
[Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Impact]

The pipeline is built and validated, and clears the >55% directional
accuracy bar out-of-sample — which, for binary market direction, is
non-trivial: the baseline is 50% and any sustained margin above it is
the line between noise and signal in this kind of problem. The thesis
itself is complete; the formal defense is the remaining step, and the
public repository release follows the defense.

Beyond the academic deliverable, the pipeline is reusable: the
walk-forward harness, the Binance ingestion, and the feature library
generalize to other crypto or financial-time-series problems and
form a starting point for future quant work.
```

### 3. score=0.638  section=lessons  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::lessons

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

### 4. score=0.681  section=approach  chunk_id=hackyeah-2025-public-transport-delays-tracker-jury-4-3-5::approach

achievement_id: `38ffd708-f1fd-4bd7-bfd7-c3ba7f3a8b74`  chunk_index: 1

```
[HackYeah 2025 — Public Transport Delays Tracker (Jury 4.3/5) — Approach]

We split the stack along clean boundaries. The backend was a Python
FastAPI service with SQLAlchemy ORM over SQLite — chosen for
hackathon speed (zero database setup) and for keeping the model
layer transparent so any team member could read or extend it. The
frontend was Angular in TypeScript, consuming REST endpoints from
the backend.

The piece I'd call out is the demo automation: one Bash script
installs all dependencies, seeds the database with sample data,
builds the frontend bundle, and launches the browser pointed at the
running app. A 24-hour hackathon doesn't reward systems that need a
human walking them through setup at presentation time. Making the
demo runnable in one command was the difference between a working
pitch and a stuttering one.
```

### 5. score=0.685  section=context  chunk_id=engineering-thesis-ml-pipeline-for-btc-market-signal-prediction::context

achievement_id: `3052f2f4-050d-429e-b667-5016aef376ed`  chunk_index: 0

```
[Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Context]

My B.Sc. engineering thesis at the Polish-Japanese Academy of
Information Technology, now complete and pending formal defense. The
topic is binary classification of Bitcoin market signals — predicting
next-period directional moves from technical-indicator features —
built as a proper walk-forward ML pipeline rather than a single
hold-out experiment. The approach is grounded in Stefan Jansen's
"Machine Learning for Algorithmic Trading" methodology. The public
repository will be linked from CV variants once the defense is held.
```


## Generated Bullets

- Buduję w Pythonie pipeline ML do klasyfikacji sygnałów rynkowych BTC na 3+ latach danych OHLCV z Binance API, z ingestią, biblioteką 30+ wskaźników technicznych i walk-forward harness jako reużywalnymi komponentami — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Approach]
- Projektuję walk-forward validation z rozszerzającymi/oknami kroczącymi i sekwencyjną ewaluacją out-of-sample, eliminując wyciek danych przez feature scaling, konstrukcję etykiet i dobór hiperparametrów — co przekłada się na dyscyplinę jakości danych w pipeline'ach czasowych — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Approach]
- Dostarczam zwalidowany pipeline przekraczający próg >55% accuracy out-of-sample na binarnej klasyfikacji kierunkowej, z komponentami (ingestion, feature library, harness walidacyjny) zaprojektowanymi jako reużywalne dla kolejnych problemów na szeregach czasowych — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Impact]
- Buduję backend w Pythonie (FastAPI + SQLAlchemy ORM) z czystym podziałem warstw oraz automatyzacją uruchomienia: jeden skrypt Bash instaluje zależności, seeduje bazę i startuje aplikację — praktyka powtarzalnego deploymentu przeniesiona z hackathonu do dyscypliny inżynierskiej — [HackYeah 2025 — Public Transport Delays Tracker (Jury 4.3/5) — Approach]
- Trzymam się standardu, w którym to harness walidacyjny, a nie sam model, decyduje o wiarygodności systemu — podejście, które przenoszę na monitoring jakości danych i ocenę pipeline'ów pod realistycznymi warunkami produkcyjnymi — [Engineering Thesis — ML Pipeline for BTC Market Signal Prediction — Lessons]

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/data-engineer-polish.md`:_
