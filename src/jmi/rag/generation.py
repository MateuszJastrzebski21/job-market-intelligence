"""Resume-bullet generator — Anthropic Claude grounded in retrieved chunks (T7).

The dossier §6 frames the generation step as the place hallucination-control
matters most: every bullet must trace to a real chunk, the system prompt
forbids invented metrics/employers/dates, and the prompt is *literal text in
the repo* so it is auditable.

Direct Anthropic SDK (no LCEL chain — dossier §5.LangChain steelman: LCEL's
wins do not apply to a single call where the prompt is the product). The
``Generator`` class is constructed once per process and reused per call.

H1/S-2: chunk text **is** sent to the model (that is the point), but the
``generate_bullets`` function never logs chunk body — only chunk ids,
counts, and a hash of the prompt for traceability.
"""

import hashlib
from typing import TYPE_CHECKING

import anthropic
import structlog
from pydantic import BaseModel, ConfigDict, Field

from jmi.config import get_settings
from jmi.rag.retrieval import ScoredChunk

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 1024

# The system prompt encodes the five rules from dossier §6.generator-prompt-shape:
# role, hallucination guard, JD-grounding, citation, lessons usage.
# Kept here as a literal string so reviewers can read the actual instructions
# and a future blog post can quote it verbatim.
SYSTEM_PROMPT = """\
You draft tailored résumé bullets for the operator's job application.

Rules — non-negotiable:

1. Ground every bullet strictly in the provided ACHIEVEMENT_CHUNKS. Do not
   invent metrics, employers, dates, technologies, or outcomes that are not
   present in those chunks.
2. If the JOB_DESCRIPTION asks for a skill or experience that is not supported
   by any chunk, OMIT it. Better to be silent than to fabricate.
3. Each bullet must trace to one or more chunks. Tag every bullet with a
   parenthetical citation listing the chunk indices it draws from, like
   "(chunks: 1, 3)". The chunks are numbered 1..N in the order I list them.
4. Prefer the chunks' own impact_metrics / tech_stack wording when present.
5. The "What I learned" sections (lessons) are factual reflection — use them
   for ownership/growth narratives, but stay specific and concrete.

Output format:

- Markdown bullet list of 3 to 5 bullets, one bullet per line, starting with "- ".
- No preamble, no postscript, no headers — just the bullets.
- Citations in parentheses at the end of each bullet.
"""


class GenerationResult(BaseModel):
    """The bullets plus the metadata needed for the smoke-check report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bullets_markdown: str = Field(min_length=1)
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    chunk_ids_in_prompt: list[str]


def format_user_message(jd: str, chunks: list[ScoredChunk]) -> str:
    """Render the user-side payload — JD + numbered chunks.

    Kept as a separate function so unit tests can pin the layout without
    pulling in the Anthropic SDK.
    """
    chunk_blocks: list[str] = []
    for i, c in enumerate(chunks, start=1):
        chunk_blocks.append(
            f"[CHUNK {i}] (score={c.score:.3f}, achievement_id={c.achievement_id})\n{c.chunk_text}"
        )
    chunks_section = "\n\n".join(chunk_blocks) if chunk_blocks else "(no chunks retrieved)"
    return f"JOB_DESCRIPTION:\n{jd.strip()}\n\nACHIEVEMENT_CHUNKS:\n{chunks_section}\n"


def _prompt_hash(jd: str, chunks: list[ScoredChunk]) -> str:
    h = hashlib.sha256()
    h.update(jd.encode("utf-8"))
    for c in chunks:
        h.update(str(c.chunk_id).encode("utf-8"))
    return h.hexdigest()[:12]


class Generator:
    """Anthropic Claude client wrapper for the bullet step.

    Instantiation reads the API key from settings — fails loudly with the same
    message ``AnthropicExtractor`` uses. The instance is reusable across calls.
    """

    def __init__(
        self,
        *,
        client: "anthropic.Anthropic | None" = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if client is None:
            api_key = get_settings().anthropic_api_key
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. Add it to .env "
                    "(copy from .env.example) before generating bullets."
                )
            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self.model = model
        self._max_tokens = max_tokens

    def generate_bullets(self, jd: str, chunks: list[ScoredChunk]) -> GenerationResult:
        """Run the bullet generation. Raises ``ValueError`` for empty inputs."""
        if not jd.strip():
            raise ValueError("jd is empty — refusing to generate without a job description")
        if not chunks:
            raise ValueError("chunks is empty — refusing to generate without retrieved chunks")

        user_message = format_user_message(jd, chunks)
        prompt_id = _prompt_hash(jd, chunks)
        log.info(
            "rag.generate.start",
            model=self.model,
            chunk_count=len(chunks),
            chunk_ids=[str(c.chunk_id) for c in chunks],
            prompt_id=prompt_id,
        )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text = _extract_text(response)
        usage = response.usage
        log.info(
            "rag.generate.done",
            model=self.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            prompt_id=prompt_id,
        )
        return GenerationResult(
            bullets_markdown=text.strip(),
            model=self.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            chunk_ids_in_prompt=[str(c.chunk_id) for c in chunks],
        )


def _extract_text(response: anthropic.types.Message) -> str:
    """Pull the assistant's text from a non-tool, non-streaming response."""
    parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)
