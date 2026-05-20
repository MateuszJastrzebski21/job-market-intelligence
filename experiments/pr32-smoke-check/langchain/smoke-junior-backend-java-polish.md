# Smoke check (LangChain): Junior Backend Java (Polish)

**Pipeline:** `jmi.rag_langchain.pipeline.RagPipeline` (PR-3.2 Worktree B)
**Language:** pl
**K:** 5
**Rerank:** on (CrossEncoderReranker with bge-reranker-base)

## Input JD

```
Poszukujemy Junior Java Developera do zespołu backendowego. Stack: Java 17+, Spring Boot, PostgreSQL, Maven/Gradle. Mile widziane: doświadczenie w pracy z REST API, testami jednostkowymi (JUnit, Mockito), wielowątkowością, oraz utrzymaniem aplikacji produkcyjnych. Cenimy umiejętność czytania cudzego kodu, dokumentowanie decyzji oraz współpracę w code review. Bonus: doświadczenie z systemami legacy i samodzielne projekty pokazujące inicjatywę.
```

## Retrieved Chunks (top-5)

### 1. score=0.703  section=lessons  chunk_id=junior-java-developer-at-red-ocean-senate-of-the-republic-of-poland-polonia-grant-platform::lessons

achievement_id: `7f69c5d3-f1be-4c8d-9f02-599b7ef71816`  chunk_index: 3

```
[Junior Java Developer at Red Ocean (Senate of the Republic of Poland Polonia Grant Platform) — Lessons]

The biggest lesson is the gap between toy code and production code in
a system serving a government client. The defect I fixed wasn't
technically complex — the technical complexity was in reasoning about
which downstream report consumers depended on the misrouted behavior
versus the correct behavior, and shipping the fix in a way that didn't
break either. That kind of constraint doesn't appear in side projects;
production code is constrained by every previous decision baked into
it.

A second lesson is about codebase navigation. Java 8 / Spring
enterprise platforms accumulate a particular shape of complexity —
deep package hierarchies, configuration scattered across XML and
annotations, legacy patterns mixed with newer ones. Becoming useful
inside that shape was as much a skill as writing the new code.
```

### 2. score=0.729  section=approach  chunk_id=junior-java-developer-at-red-ocean-senate-of-the-republic-of-poland-polonia-grant-platform::approach

achievement_id: `7f69c5d3-f1be-4c8d-9f02-599b7ef71816`  chunk_index: 1

```
[Junior Java Developer at Red Ocean (Senate of the Republic of Poland Polonia Grant Platform) — Approach]

The work is a mix of feature extension on an existing system and
defect resolution under production constraints. The single piece I'd
single out is a critical data-routing bug in the report configuration
module: report fields were being resolved through the wrong code path,
producing incorrect aggregations in generated outputs. The fix was not
a one-line patch — the underlying issue was that field resolution was
mixed with unrelated configuration logic, so I redesigned the backend
flow and introduced a dedicated REST endpoint that separates field
resolution into its own concern, with the report configuration code
calling into it cleanly. Alongside that, I've worked on the report
generation pipeline (adding new data fields and Excel/XML export
logic) and on the JPA/Hibernate layer for new domain requirements.
```

### 3. score=0.704  section=approach  chunk_id=hackyeah-2025-public-transport-delays-tracker-jury-4-3-5::approach

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

### 4. score=0.648  section=impact  chunk_id=quantfolio-javafx-multi-asset-portfolio-simulator::impact

achievement_id: `185e7ab1-9674-4794-ad14-a3e00e26e121`  chunk_index: 2

```
[Quantfolio — JavaFX Multi-Asset Portfolio Simulator — Impact]

The project is a complete working desktop application — runnable,
testable (JUnit 5 suite via Maven), documented. It's referenced in
the software-engineering variant of my CV as evidence of OOP and
design-pattern fluency in Java, and the GitHub repository
(github.com/MateuszJastrzebski21/Quantfolio) is publicly available.
```

### 5. score=0.786  section=context  chunk_id=junior-java-developer-at-red-ocean-senate-of-the-republic-of-poland-polonia-grant-platform::context

achievement_id: `7f69c5d3-f1be-4c8d-9f02-599b7ef71816`  chunk_index: 0

```
[Junior Java Developer at Red Ocean (Senate of the Republic of Poland Polonia Grant Platform) — Context]

Red Ocean is the Warsaw-based software house I joined as a Junior Java
Developer in March 2026, working on-site on a production Java 8 / Spring
enterprise platform that serves the Senate of the Republic of Poland's
Polonia grant programme. The platform handles the full grant-application
lifecycle — submission, evaluation, reporting — and at the time I joined
had over 890 submitted proposals flowing through it. The team uses
standard enterprise Java tooling (Spring, JPA/Hibernate, Angular
frontend, PostgreSQL) under a Scrum/Agile process.
```


## Generated Bullets

- Maintain and extend a production Java 8 / Spring enterprise platform serving the Senate of the Republic of Poland's Polonia grant programme, working with JPA/Hibernate and PostgreSQL under a Scrum/Agile process — [Junior Java Developer at Red Ocean — Context]
- Resolved a critical data-routing defect in the report configuration module by redesigning the backend flow and introducing a dedicated REST endpoint that isolates field resolution from unrelated configuration logic, shipping the fix without breaking existing downstream report consumers — [Junior Java Developer at Red Ocean — Approach]
- Extended the report generation pipeline with new data fields and Excel/XML export logic, and evolved the JPA/Hibernate layer to support new domain requirements on the live grant-application platform — [Junior Java Developer at Red Ocean — Approach]
- Navigate a legacy Java 8 / Spring codebase with deep package hierarchies and configuration spread across XML and annotations, reasoning carefully about which downstream consumers depend on existing behavior before changing it — [Junior Java Developer at Red Ocean — Lessons]
- Built Quantfolio, a complete JavaFX multi-asset portfolio simulator in Java with a JUnit 5 test suite via Maven, demonstrating initiative on a self-directed project with OOP and design-pattern fluency (github.com/MateuszJastrzebski21/Quantfolio) — [Quantfolio — JavaFX Multi-Asset Portfolio Simulator — Impact]

## Notes

_Operator labels:_ grounded / partial / hallucinated

- bullet 1:
- bullet 2:
- bullet 3:
- bullet 4:
- bullet 5:

_Side-by-side comparison with Worktree A's `experiments/pr32-smoke-check/junior-backend-java-polish.md`:_
