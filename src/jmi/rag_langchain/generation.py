"""Resume-bullet generation via an LCEL chain.

Composes `ChatPromptTemplate | ChatAnthropic | StrOutputParser` — the standard
LangChain Expression Language chain. The system prompt encodes the five rules
the dossier (§6) calls out: role, hallucination guard, JD-grounding, citation
by slug, and the `lessons` usage rule.

The chain is constructed eagerly but the ChatAnthropic client is the one that
lazy-loads the API key from `ANTHROPIC_API_KEY`. Tests pass in a fake chain so
no real API call is made during unit tests; the smoke check (T11) exercises the
real model.

Security (S-2): logs structural fields (model id, chunk count) — never the
retrieved chunk text or the generated bullets.
"""

from typing import TYPE_CHECKING

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

if TYPE_CHECKING:
    from jmi.rag_langchain.retrieval import ScoredChunk

DEFAULT_MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """\
You are drafting tailored résumé bullet points for a job application.

Operating rules — non-negotiable:
1. Use ONLY the achievements provided below. Do not invent metrics, employers,
   dates, technologies, or outcomes that are not in the achievements.
2. Each bullet must map to a requirement in the job description.
3. Prefer the achievements' own impact_metrics, tech_stack, and language.
4. If a requirement in the job description has no matching achievement, omit
   that requirement rather than fabricating a bullet for it.
5. Use the `[Title]` header in each chunk to cite the source achievement at
   the end of the bullet, e.g. "— [Built a payment matcher]".
6. The `lessons` section is the reflective/learning source — use it for
   ownership and growth narrative, but only when the lesson is factual.
7. Output 3 to 5 bullets, one per line, starting with "- ".

Tone: present-tense, active voice, hiring-manager-readable.
"""

USER_PROMPT_TEMPLATE = """\
Job description:
<job_description>
{job_description}
</job_description>

Retrieved achievements (top-{k}):
<achievements>
{achievements}
</achievements>

Draft 3–5 tailored bullets following the operating rules.\
"""


def format_achievements(chunks: list["ScoredChunk"]) -> str:
    """Render scored chunks into a numbered block for the prompt."""
    lines: list[str] = []
    for i, c in enumerate(chunks, start=1):
        lines.append(f"## Achievement {i} (section={c.section}, score={c.score:.3f})")
        lines.append(c.chunk_text)
        lines.append("")
    return "\n".join(lines).rstrip()


log = structlog.get_logger(__name__)


def build_chain(
    model_name: str = DEFAULT_MODEL, max_tokens: int = 800
) -> Runnable[dict[str, object], str]:
    """Construct the LCEL chain: prompt | model | str parser.

    Returns a Runnable accepting the dict `{"job_description": str, "achievements": str,
    "k": int}` and yielding a string of bullet text.
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE),
        ]
    )
    model = ChatAnthropic(model=model_name, max_tokens=max_tokens)
    return prompt | model | StrOutputParser()


def generate_bullets(
    job_description: str,
    chunks: list["ScoredChunk"],
    *,
    chain: Runnable[dict[str, object], str] | None = None,
    model_name: str = DEFAULT_MODEL,
) -> str:
    """Run the LCEL chain on a JD + retrieved chunks and return the bullet text.

    Tests pass `chain=` to skip the live API; production callers leave it None
    and the default chain is built using `build_chain`.
    """
    chain = chain or build_chain(model_name=model_name)
    inputs = {
        "job_description": job_description,
        "achievements": format_achievements(chunks),
        "k": len(chunks),
    }
    result = chain.invoke(inputs)
    log.info(
        "rag.lc.generate.done",
        model=model_name,
        chunk_count=len(chunks),
        bullet_chars=len(result),
    )
    return result
