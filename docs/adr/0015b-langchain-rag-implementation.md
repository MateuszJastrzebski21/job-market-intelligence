# ADR-0015b: LangChain RAG Implementation (PR-3.2 Worktree B)

**Status:** Proposed / pending PR-3.2 merge
**Date:** 2026-05-20
**Context of:** the `jmi.rag_langchain` package — chunker, embedder, ingest,
retriever, reranker, generation, and end-to-end pipeline, all reimplementing
PR-3.2's RAG flow using LangChain 0.3.x primitives. Pairs with ADR-0015a
(custom RAG, Worktree A) and feeds ADR-0015 (synthesis, Worktree C).

## Context

PR-3.2 produces *two* RAG implementations against the same achievement corpus —
a custom one (ADR-0015a) and a LangChain one (this ADR) — so the comparison ADR
(ADR-0015, Worktree C) can rank them on the same benchmark with the same
ground truth.

Worktree B's job is the LangChain side. The dossier
(`docs/research/pr-3.2-rag-comparison-dossier.md`) frames the comparison and
predicts the failure modes. This ADR records the LangChain implementation's
concrete choices, the surprises encountered in building it, and where it lands
against the dossier's predictions before the comparison ADR weighs both
implementations.

The dossier's bottom line — "a framework bets its opinions match yours;
JMI committed to different, typed opinions, so the bet doesn't pay here" (§5)
— is the operating hypothesis. This ADR notes where the LangChain build
*confirmed* the hypothesis, and where it *surprised* by working better than
expected.

## Decision

Adopt LangChain 0.3.x as the framework for Worktree B's reimplementation,
pinned and documented in this ADR. **Each component** below maps the
LangChain primitive used to the custom-side equivalent it replaces, with the
trade-off recorded.

The package lives at `src/jmi/rag_langchain/` and mirrors Worktree A's public
surface (`RagPipeline.retrieve_top_k`, `RagPipeline.generate_bullets`) so the
benchmark harness can swap implementations without touching itself.

### 1. Dependency stack (pinned)

| Package | Pin | Role |
| --- | --- | --- |
| `langchain` | `>=0.3,<0.4` | chains, retrievers, `ContextualCompressionRetriever`, `CrossEncoderReranker` |
| `langchain-core` | `>=0.3,<0.4` | `Document`, `BaseRetriever`, `Embeddings`, `Runnable`, prompts, output parsers |
| `langchain-postgres` | `>=0.0.14,<0.1` | `PGEngine`, `PGVectorStore` — current API; *not* the deprecated `PGVector` (`langchain-community`) |
| `langchain-huggingface` | `>=0.1,<0.2` | `HuggingFaceEmbeddings` |
| `langchain-anthropic` | `>=0.3,<0.4` | `ChatAnthropic` |
| `langchain-text-splitters` | transitive | `RecursiveCharacterTextSplitter` for the sliding-window variant |

The 0.3.x line was chosen — the orchestrator named it explicitly and `0.3.30`
is still the latest 0.3 release, even though `langchain` has since opened a
1.x line. Worktree B does *not* test 1.x; that is itself an ADR-0015 (or
follow-up) decision.

### 2. Forced pgvector downgrade — RECONSIDER

Adding `langchain-postgres>=0.0.14` forced the project's `pgvector` pin from
`>=0.4.2` to `>=0.3.6,<0.5`. `langchain-postgres 0.0.17` (the latest 0.0.x)
still pins `pgvector<0.4`. Existing JMI code only imports
`pgvector.sqlalchemy.Vector` — stable across both major versions — so JMI's
behaviour does not change. But the *pin* itself is a finding: a single new
framework dependency pulled the whole project's pgvector version one major
behind upstream.

**RECONSIDER** if `langchain-postgres` ships a `pgvector>=0.4`-compatible
line before PR-3.2 merges. The downgrade is the dossier-predicted
"abstraction tax" cashed before any feature code (§5 / "moderate" lock-in).

### 3. Per-section chunking via direct `Document` construction

```python
# src/jmi/rag_langchain/chunking.py
def chunk_achievement(achievement: Achievement) -> list[Document]:
    docs = []
    for index, section in enumerate(SECTION_ORDER):
        body = getattr(achievement, section)
        if not body or not body.strip():
            continue
        header = f"[{achievement.title} — {_SECTION_LABEL[section]}]"
        docs.append(Document(
            page_content=f"{header}\n\n{body.strip()}",
            metadata={"achievement_id": str(achievement.id),
                      "chunk_index": index,
                      "section": section,
                      "title": achievement.title},
        ))
    return docs
```

The dossier predicted this (§5 "Custom chunker → LangChain TextSplitter"):
*"LangChain's splitters consume raw markdown strings, but JMI has none at
chunk time — PR-3.1's parser already turned it into a typed Achievement.
Using the splitter means re-serialising the object back to markdown."* — so
we *don't* use a splitter on the primary path. We construct `Document`
objects directly from the typed fields. LangChain wins nothing here over the
custom side; both implementations end up with the same four-element list.

The static `[Title — Section]` header is the free Contextual Retrieval pattern
(dossier §1.a → Anthropic Contextual Retrieval), prepended on both sides for
parity.

The sliding-window variant *does* use `RecursiveCharacterTextSplitter` — but
only for the mini-experiment in `chunk_achievement_sliding`. It's character-
based (LangChain's only out-of-box splitter without an extra `tiktoken`
dep), so the size parameter does not map cleanly onto the embedder's token
budget — that mismatch is itself part of the comparison surface.

### 4. PGVectorStore on a *separate* collection table — RECONSIDER

The biggest decision in Worktree B, called out by the orchestrator T4
explicitly. LangChain's `PGVectorStore` (from `langchain-postgres`) owns its
own schema:

```
langchain_id           UUID  PK
content                TEXT       -- the chunk body
embedding              VECTOR(N)  -- the embedding
langchain_metadata     JSONB      -- everything else
```

JMI's existing `achievement_embeddings` (PR-3.1, ADR-0014) is:

```
id                     UUID  PK
achievement_id         UUID  FK → achievements.id  ON DELETE CASCADE
chunk_index            INT
chunk_text             TEXT
embedding              VECTOR(384)
created_at             TIMESTAMP
UNIQUE(achievement_id, chunk_index)
```

`PGVectorStore.create_sync` takes `content_column`/`embedding_column`/`id_column`
overrides and *almost* lines up — but it cannot honour the existing
`UNIQUE(achievement_id, chunk_index)` constraint or the FK cascade. To put
PGVectorStore on the existing table either:

- **(B1)** I write a custom `VectorStore` subclass that respects the FK +
  unique constraint — at which point Worktree B is no longer "LangChain
  idiomatic," and the comparison is "custom RAG vs custom RAG wrapped in a
  LangChain class name."
- **(B2)** I drop the FK + unique constraint from `achievement_embeddings` so
  PGVectorStore can sit on it — corrupting Worktree A's invariants for the
  sake of B's framework.

I chose **option A from the orchestrator spec** — a sibling table
`langchain_achievement_embeddings` on the same database. `PGEngine.init_vectorstore_table`
creates it with LangChain's default columns; `PGVectorStore.create_sync` binds
to it; `ingest_chunks` writes deterministic UUID5 ids derived from
`(achievement_id, chunk_index)` so re-ingest upserts rather than duplicates.

Cost: each chunk is now stored *twice* (once per implementation) for the
duration of the comparison — for ~80 chunks × 384 floats × 4 bytes ≈ **120 KB
total**, plus the duplicated `chunk_text`. Trivial.

**Benefit (the comparison material):** the schema collision the dossier
predicted (§5 "the sharpest lock-in finding") is now *visible* — two
side-by-side tables in the same database, both populated by the same chunker
+ embedder. The blog (Angle B per dossier §7) can screenshot the two
schemas next to each other.

**RECONSIDER** if a follow-up PR wants Worktree B to consume Worktree A's
canonical chunks via a read-only adapter, side-stepping the duplication. The
trade-off is that it would *hide* the comparison finding; the operator
should weigh that.

### 5. HuggingFaceEmbeddings adapter — a tie

```python
# src/jmi/rag_langchain/embedding.py
HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    encode_kwargs={"normalize_embeddings": True, "show_progress_bar": False},
)
```

Embedder is `BAAI/bge-small-en-v1.5` — the dossier-recommended drop-in
upgrade from `all-MiniLM-L6-v2` that keeps 384-dim (no pgvector schema
change). LangChain's `Embeddings` ABC is `embed_documents` +
`embed_query` — the same two methods Worktree A's `CustomEmbedder`
exposes. The dossier called this a tie (§5 "Custom embedder → LangChain
Embeddings") and the build confirmed it: this single component is the one
place LangChain costs nothing.

What stays hidden: the asymmetric-query-prefix story. BGE-small/base v1.5
*don't* require an instruction prefix, so the issue does not bite here.
With BGE-large or `intfloat/e5-*`, the prefix lives inside the `Embeddings`
subclass (`HuggingFaceEmbeddings.query_instruction`) — visible but easily
forgotten.

### 6. Retriever wrapping `PGVectorStore.similarity_search_with_score`

```python
# src/jmi/rag_langchain/retrieval.py
def retrieve(store, query, k=5) -> list[ScoredChunk]:
    raw = store.similarity_search_with_score(query, k=k)
    ...
    return [ScoredChunk(..., score=1.0 - distance) for doc, distance in raw]
```

LangChain returns `(Document, distance)`; we invert to `score = 1 - distance`
so higher = better, matching Worktree A's `ScoredChunk` contract.

**The dossier called the observability loss out, and the build confirmed
it.** LangChain hides the SQL operator (`<=>` for cosine distance), the
index choice (HNSW vs IVFFlat vs no index), and the `EXPLAIN` plan inside
`similarity_search`. Worktree A executes an explicit
`ORDER BY embedding <=> :q LIMIT :k` — every layer of that query is in the
diff and a `psql \dt` away. Worktree B's equivalent is a method call into
`langchain-postgres` source.

For a debugging-heavy workflow (or a "teach me how pgvector works" learning
artifact), the custom side wins — this is the §5 finding restated. For a
production app already familiar with pgvector internals, the hidden layer
costs nothing.

### 7. Reranker via `CrossEncoderReranker` — design choice on `BaseCrossEncoder`

```python
# src/jmi/rag_langchain/reranking.py
class SentenceTransformersCrossEncoder(BaseCrossEncoder):
    def score(self, text_pairs):
        return [float(x) for x in self._load_model().predict(list(text_pairs)).tolist()]

def compose_with_reranker(base_retriever, top_n=5, model=None):
    reranker = CrossEncoderReranker(model=model or SentenceTransformersCrossEncoder(),
                                    top_n=top_n)
    return ContextualCompressionRetriever(base_compressor=reranker,
                                          base_retriever=base_retriever)
```

The community-blessed adapter is `langchain-community.HuggingFaceCrossEncoder`,
which would force adding `langchain-community` (a heavy meta-package) just for
one class. Instead a tiny `SentenceTransformersCrossEncoder` subclass of
`BaseCrossEncoder` wraps the existing `sentence-transformers.CrossEncoder`
directly — `sentence-transformers` is already a JMI dependency.

This is a small win for the framework's *core* design (`BaseCrossEncoder` is
a clean ABC with a single `score` method) and a small loss for its *partner-
package* defaults (the obvious adapter pulls in too much). The dossier did
not flag this specifically; mark it as a finding to add to ADR-0015.

The drop-in seam orchestrator T6 calls for is `compose_without_reranker(base)`,
which just returns the retriever unchanged. The pipeline's `rerank=True`/
`False` branch is then a one-statement swap.

### 8. Pipeline: oversample for reranking, then *re-score* to recover scores

Two surprises in the pipeline composition that ADR-0015 should record.

**Surprise 1.** `ContextualCompressionRetriever` returns `list[Document]` —
*not* scored documents. The cross-encoder's scores are computed and used for
sorting but never surfaced. Worktree A's reranker returns
`list[ScoredChunk]` with the cross-encoder score attached, so the benchmark
harness can read per-chunk scores. To match Worktree A's contract, the
LangChain pipeline calls `similarity_search_with_score` a *second* time
against the same candidate set and aligns the reranked docs by `chunk_id` to
recover the *bi-encoder* score. The cross-encoder score is lost. Not a
correctness problem (ranking is correct) but a real ergonomic loss — and a
clean blog example of "the framework's abstraction left signal on the
floor."

**Surprise 2.** `ContextualCompressionRetriever` requires a `BaseRetriever`,
not a `VectorStore`. `PGVectorStore.as_retriever(search_kwargs={"k": K})`
emits one, with `k` fixed at construction time. To over-sample the
bi-encoder before reranking (dossier §4 "retrieve top-50, rerank to top-5"
— scaled to 4×k=20 for our small corpus), we have to build a *new*
retriever per call with the larger `k`. The custom side just passes `k` as a
function argument. The cost is mild — one extra object allocation per
reranked call — but it is friction the dossier did not predict.

### 9. Generation via LCEL — `prompt | model | parser`

```python
# src/jmi/rag_langchain/generation.py
prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT),
                                            ("human", USER_PROMPT_TEMPLATE)])
chain = prompt | ChatAnthropic(model="claude-opus-4-7", max_tokens=800) | StrOutputParser()
```

LCEL composes the three pieces with operator overloads (`|`). The system
prompt is the dossier §6 contract: ground bullets in the provided
achievements only, cite the title at the end of each bullet, prefer the
achievement's own metrics/tech-stack, omit (don't fabricate) when a JD
requirement has no match. This is *identical* to Worktree A's generation
prompt — the prompt is the product, the framework around it does not change
its content.

The dossier predicted this was a tie or a win for direct Anthropic SDK (§5
"Generation"). The build confirms a tie *for a single one-shot call*. LCEL's
real wins — streaming, retries, batching, structured-output binding,
multi-step chains — do not apply to a non-streaming, single-call generator
on top of retrieved chunks.

The LangChain Anthropic adapter `ChatAnthropic` *does* hide the request body
— there is no place in the code where the literal system message + user
message + max_tokens get visible. The custom side has them as plain
arguments to `client.messages.create(...)`. For a generator where "prompt
engineering *is* the product," that hiding is a real observability loss for
debugging a hallucination — you must trust the LangChain layer to send what
your code says it sends. **This is the strongest argument in this ADR for
the direct Anthropic SDK** even given LCEL's other niceties.

### 10. CLI surface (deferred)

Worktree A ships `jmi rag-embed` and `jmi rag-query` Typer commands.
Worktree B does *not* ship CLI commands in this PR — the public surface is
the `RagPipeline` class consumed by Worktree C's benchmark harness and the
T11 smoke check. **Adding `jmi rag-lc-embed` / `jmi rag-lc-query` is left
to a follow-up PR** if the comparison concludes Worktree B is worth shipping
as a user-visible alternative; otherwise the dual CLI is dead weight in a
single-implementation merge.

## Consequences

### Positive

- The two implementations expose the same public surface, so Worktree C's
  benchmark drops in unmodified.
- The schema-collision finding is structurally visible: both tables live in
  the same database, the diff is reproducible, the blog can screenshot it.
- 45 unit tests cover chunker, embedder adapter, ingest, retrieval,
  reranker, generation, and pipeline composition — all DB-free and
  model-free (no live API calls in CI).

### Negative

- `pgvector` pin downgraded from `>=0.4.2` to `>=0.3.6` to admit
  `langchain-postgres`. RECONSIDER (§2).
- Chunk content is stored twice while both implementations coexist (~120 KB).
  RECONSIDER (§4).
- The reranker's cross-encoder score is dropped before reaching the public
  pipeline interface, so the benchmark cannot read per-chunk *reranker*
  scores — only the post-rerank ranking. The custom side surfaces both.
- Two LangChain-version churn artifacts are already locked-in: (a) the 0.3.x
  vs 1.x split, (b) the deprecated `langchain-community.PGVector`
  → `langchain-postgres.PGVectorStore` migration. Worktree B is on the
  current line; the legacy mini-experiment (T10) intentionally exercises the
  deprecated path so the cost of one such migration is recorded.

### Neutral

- LangChain's `Embeddings` ABC and `BaseCrossEncoder` are well-designed
  seams worth copying into a custom build even when no LangChain code is
  shipped (matches the dossier's steelman in §5).

## Cross-references to the dossier

- **§1 — chunking.** Per-section is the recommendation; the build confirms
  LangChain's `MarkdownHeaderTextSplitter` would round-trip the typed
  `Achievement` back to markdown for no benefit. (Implementation §3.)
- **§2 — embedder.** `bge-small-en-v1.5` is a tie with the custom side
  (same model, same interface). (Implementation §5.)
- **§3 — retrieval metrics.** Out of scope for this ADR — Worktree C's
  ADR-0015 owns the benchmark and its CIs.
- **§4 — reranking.** "Drop-in seam past the first cut" — Worktree B
  implements that seam with `compose_with_reranker` / `compose_without_reranker`.
  (Implementation §7.)
- **§5 — LangChain comparison surface.** This ADR is the LangChain side of
  the comparison; ADR-0015 reads §5 plus both this ADR and ADR-0015a side
  by side. The schema-ownership prediction (§5 / "the sharpest lock-in
  finding") is confirmed and made structural (Implementation §4); the
  observability loss in retrieval (§5 / "Custom wins on observability") is
  confirmed (Implementation §6); the generation tie with direct Anthropic
  SDK (§5 / "Generation") is confirmed (Implementation §9).
- **§6 — generation.** The hallucination guard + citation-by-slug system
  prompt is identical across implementations. (Implementation §9.)
- **§7 — blog angles.** This ADR's findings feed Angle A (the dual build)
  and Angle B (schema ownership) directly.

## References

- ADR-0015a (Worktree A — custom RAG implementation)
- ADR-0015 (Worktree C — comparison synthesis, written *after* both sides)
- `docs/research/pr-3.2-rag-comparison-dossier.md`
- ADR-0014 (`achievement_embeddings` schema)
- `src/jmi/rag_langchain/` (this ADR's implementation)
- `tests/rag_langchain/` (45 unit tests)
