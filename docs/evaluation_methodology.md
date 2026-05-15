# Extraction Quality Evaluation — Methodology

How the `jmi evaluate` command measures LLM extraction quality, and how to
read its output. See ADR-0010 for the architectural rationale.

## Purpose

The extractor (`jmi extract`) turns a raw `JobPosting` into a structured
`JobExtract` using Claude. Until PR16 there was no objective measure of how
good those extracts are — only an eyeballed quality investigation
(`docs/next-session.md`, commit `6d466a4`) which spotted a critical
salary-recall bug.

The evaluation framework closes that gap. It compares extracts against
hand-labelled ground truth, computes per-field metrics, and prints a report.
This makes prompt changes (PR17) and re-extraction (PR18) measurable rather
than anecdotal.

PR16 is **baseline-only**: it measures, it does not change extraction.

## Schema — `docs/ground_truth/phase1_seed.json`

The seed file is a JSON array. Each entry pairs a posting with the values a
perfect extractor should produce:

```jsonc
{
  "id": "hf-0CE9E806CC",        // human-readable label id
  "source": "huggingface",
  "source_job_id": "...",        // OPTIONAL — see below
  "posting": { "title": "...", "company": "...", "description_text": "..." },
  "expected": {                  // the gold label
    "seniority": "mid",
    "tech_stack": ["Python", "PyTorch"],
    "salary_min": null, "salary_max": null, "salary_currency": null,
    "remote_policy": "remote",
    "years_experience_min": null,
    "employment_type": "full_time"
  },
  "notes": "reasoning for the label"
}
```

### `source_job_id` and label matching

A label is matched to a DB extract by `(source, source_job_id)`. The original
3 HuggingFace entries predate the framework and carry only a human-readable
`id`, from which the real `source_job_id` cannot be recovered. Such entries
are reported as **unmatchable** (`reason=id_only`) and excluded from metrics.

**Future hand-written labels should always include `source_job_id`** so they
can be evaluated. The field is optional purely for backward compatibility.

## Metrics

| Field(s) | Metric | Definition |
|---|---|---|
| `seniority`, `remote_policy`, `employment_type` | `exact_match` | `actual == expected`; both-`null` is a match |
| `years_experience_min` | `numeric_match_or_both_null` | exact integer equality, or both `null` |
| `tech_stack` | `jaccard_similarity` | `|A ∩ B| / |A ∪ B|`, case-insensitive |
| `salary_min`/`salary_max` | `salary_match` | each endpoint within ±10% relative tolerance; a `null` expected endpoint matches only a `null` actual one |

- **Jaccard, both lists empty → `1.0`.** Nothing was expected and nothing was
  produced — that is perfect agreement, not a failure.
- **`salary_match`, all-null on both sides → match.** The extractor correctly
  declined to invent a salary.
- **tech_stack pass threshold:** a tech_stack score `>= 0.8` counts as a
  "pass" in the report's pass-rate line. The threshold is reporting sugar; the
  headline number is the mean Jaccard.

### Salary recall

Recall answers "of the salaries the label has, how many did the extractor
capture?":

```
salary_min recall = (# evaluable entries where label has salary_min
                      AND extract captured a non-null salary_min)
                   / (# evaluable entries where label has salary_min)
```

`salary captured WITH correct currency` further splits captured salaries by
whether `salary_currency` also matches the label — this isolates the
currency-normalization problem (e.g. `PLN/h` vs `PLN/month`) that PR18
targets.

## Reading the report

`jmi evaluate` prints four parts:

1. **Header** — total labels, how many had an extract, how many did not.
2. **Per-field accuracy** — exact-match % for the categorical/numeric fields.
3. **Per-field similarity** — tech_stack Jaccard average, range, median, and
   ≥0.8 pass rate.
4. **Salary recall** — the critical-metric section, flagged with `<!>` when
   recall drops below 50%.
5. **Per-source breakdown** — the same headline numbers split jjit vs
   huggingface.

`--show-unmatched` appends a debugging list of labels that could not be
scored, each with a remediation hint. `--output json` emits the whole report
as JSON for CI gating or trend tracking.

## Known biases (at time of writing)

- **The current seed has only 3 HuggingFace few-shot entries, all id-only.**
  On today's seed the report shows `total=3, evaluable=0` — there is nothing
  to score yet. The framework is in place; labelled data is future manual
  work.
- **All 3 seed entries have `salary_*` = null.** Even once matched, salary
  recall has a denominator of 0 and reports `N/A`. Measuring the salary bug
  requires labelled JJIT entries (PR17/18 roadmap).
- **Few-shot overlap.** The same 3 entries seed the extractor's few-shot
  prompt. Evaluating an extract of a posting that was itself a few-shot
  example would inflate accuracy. Future labels should be postings *not* used
  as few-shot examples.

## Known limitations

`tech_stack` matching is **exact after lowercasing** — there is no alias or
synonym normalization. Semantic equivalents score as distinct entries:
`AWS` vs `Amazon Web Services`, `GCP` vs `Google Cloud Platform`,
`NVIDIA CUDA` vs `CUDA`. This understates true tech_stack quality whenever the
label and the extract pick different-but-equivalent names.

Mitigation for now: **ground-truth labels should use the shorter, common
form** (`AWS`, `GCP`, `Python`). Alias normalization is deliberately out of
scope for PR16 and may be revisited if it proves to be a material source of
noise.

## Edge cases handled

- **Empty seed** → report `status="no_labels"`, all counts zero, exit 0.
- **Label with no matching posting** → `reason=no_posting`, excluded from
  metrics, counted in "without extract".
- **Posting exists but was never extracted** → `reason=no_extract`.
- **Label is id-only** → `reason=id_only`.
- **Multiple extracts for one posting** → the most recent (`extracted_at`)
  wins. Re-extraction (PR18) produces newer rows; older extracts stay for
  audit but are not evaluated.
- **A metric with a zero denominator** (e.g. salary recall with no labelled
  salaries) → rendered `N/A`, never a divide-by-zero.

## Reference

- Quality investigation that motivated this framework:
  `docs/next-session.md`, commit `6d466a4`.
- Architectural rationale: `docs/adr/0010-evaluation-framework.md`.
