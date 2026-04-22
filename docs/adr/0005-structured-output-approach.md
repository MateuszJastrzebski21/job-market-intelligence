# ADR-0005: Structured Output Approach for LLM Extraction

**Status:** Accepted
**Date:** 2026-04-22
**Context of:** Week 1 LLM extractor (`src/jmi/extractors/anthropic.py`)

## Context

The LLM extractor must turn unstructured job descriptions into validated
`JobExtract` rows (seniority, tech stack, salary bands, remote policy, etc.).
The Anthropic API offers three ways to enforce structure on the response.
We need one; mixing them inside a single call is not supported.

## Decision

Use **`client.messages.parse()` with a Pydantic `JobExtractSchema`** as the
`output_format`.

## Consequences

**Positive**

- Zero boilerplate: `response.parsed_output` is already a validated Pydantic
  instance. No `json.loads(text)` + `Schema.model_validate(...)`.
- Schema mismatches surface as `pydantic.ValidationError` at parse time, not
  as silent drift we discover later in DB queries.
- Works with adaptive thinking and prompt caching without ceremony; cache
  invariant only cares about the rendered prefix, not the output channel.
- One source of truth — the Pydantic schema — drives both LLM output
  validation and local tests.

**Negative**

- Restricted JSON Schema subset: no recursive schemas, no `minLength` /
  `minimum`, no `additionalProperties: true`. Fine for our flat schema;
  would hurt if extract grew nested.
- First request for a new schema pays a one-time compilation cost (24h
  cache on the API side). Amortized across 9+ extracts per run.
- Refusal (`stop_reason: "refusal"`) can still produce non-conforming
  output — we must check `stop_reason` before trusting `parsed_output`.

## Alternatives Considered

### (a) Tool use (`tools=[...]`, force `tool_choice`)

- **Plus:** Works on all models including ones without structured output
  support. Natural fit when the LLM also *uses* tools in the same call.
- **Minus:** Forces conceptual mismatch — we're not invoking a function,
  we're extracting data. Adds the extract step into a multi-turn loop
  that must handle `tool_use` / `tool_result` roundtrips just to get
  one payload back. Higher prompt overhead (the tool definition renders
  into every request). No automatic Pydantic validation.
- **When to pick:** LLM genuinely needs to pick *between* multiple
  actions and returning a structured extract is one of several options.

### (b) JSON mode (`output_config.format: {type: "json_schema"}`) + manual parse

- **Plus:** Supports the full raw JSON Schema syntax, not Pydantic's
  translation of it. Fine-grained control if we need quirks the Pydantic
  adapter doesn't emit.
- **Minus:** Handwritten schema duplicates the Pydantic model we already
  have for `JobExtract`. Two places to keep in sync = bug farm. Manual
  `json.loads` + `model_validate` = more code, same result.
- **When to pick:** Schema cannot be expressed in Pydantic (recursive
  type, exotic `anyOf` tree, vendor-specific constraints), or we're
  language-agnostic and can't assume Pydantic on the consumer side.

### (c) `client.messages.parse()` + Pydantic — **chosen**

- **Plus:** Single source of truth, auto-validation, SDK-idiomatic.
- **Minus:** Tied to Pydantic v2 (we already are) and the Anthropic SDK
  (we already are).

## References

- Anthropic skill: `shared/tool-use-concepts.md` §Structured Outputs
- Anthropic skill: `python/claude-api/tool-use.md` §JSON Outputs (Pydantic)
