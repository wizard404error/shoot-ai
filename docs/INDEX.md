# Kawkab AI — Documentation Index

> **Purpose:** this project has 10+ markdown documents. New readers (humans or AI assistants) waste time figuring out which one to read first. This index is the map.

---

## Quick links by audience

### "I just want to install and try it"
→ **[README.md](../README.md)**
Install, prerequisites, quick start, first run. Start here. Current state: **v0.8.3**.

### "What's actually working and what isn't?"
→ **[STATUS.md](../STATUS.md)**
The honest, brutal status report. Per-feature truth table. Last updated: v0.8.3.

### "What should I build next?"
→ **[PLAN.md](../PLAN.md)**
The next-version build plan. Targets v0.9.0. Updated when a new arc opens.

### "How do I package and ship a release?"
→ **[BUILD.md](../BUILD.md)**
PyInstaller + Inno Setup workflow. Windows installer build steps.

### "I'm an AI assistant working on this project — what are the rules?"
→ **[AGENTS.md](../AGENTS.md)**
Graphify integration, mandatory rules, and how to use the knowledge graph.

### "What's the long-term product plan?"
→ **[EXECUTION_PLAN.md](../EXECUTION_PLAN.md)**
The seven-arc plan toward professional sports-analytics parity. Months-level.

### "What's the current cycle of work and what's the backlog?"
→ **[ITERATION_LOG.md](../ITERATION_LOG.md)**
The operating system: cycle loop, backlog of 63 targets, quality bar, cycle log.

### "What's wrong with this project, and what should I fix first?"
→ **[REVIEW.md](../REVIEW.md)**
Independent code review. Diagnoses the 30+ weaknesses. Read this if you're deciding what to work on.

### "What are the gaps vs StatsBomb / Hudl / Wyscout / SciSports?"
→ **[PROFESSIONAL_AUDIT.md](../PROFESSIONAL_AUDIT.md)**
Feature-by-feature gap analysis vs the pro tools. Used to build the Iteration Log backlog.

### "What did the previous AI review find?"
→ **[kawkab-ai-review.md](../kawkab-ai-review.md)**
Earlier independent review. Some of its findings are now resolved in v0.8.3; check STATUS.md before acting on it.

---

## Document authority

When docs disagree (they do, often), here's the precedence:

| Question | Authoritative source |
|---|---|
| What's the current version? | `STATUS.md` (most detailed, most recent) |
| What works right now? | `STATUS.md` |
| What's installed and how? | `README.md` |
| What's planned next? | `PLAN.md` (current arc only) |
| What should be built? | `ITERATION_LOG.md` (backlog) |
| What's wrong? | `REVIEW.md` + `PROFESSIONAL_AUDIT.md` |
| How to build a release? | `BUILD.md` |
| How to work in this repo (AI)? | `AGENTS.md` |

If `STATUS.md` is wrong, fix `STATUS.md` first. If `README.md` and `STATUS.md` disagree on version, **trust `STATUS.md`**.

---

## Source of truth for each file

| Doc | Owned by | Update when |
|---|---|---|
| `README.md` | maintainer | a feature changes install / first-run |
| `STATUS.md` | maintainer | a feature lands or a known issue resolves |
| `PLAN.md` | maintainer | a new arc opens or current arc completes |
| `BUILD.md` | maintainer | the installer recipe changes |
| `AGENTS.md` | maintainer | the AI workflow changes |
| `EXECUTION_PLAN.md` | Mavis (AI assistant) | arcs are added/closed |
| `ITERATION_LOG.md` | Mavis (AI assistant) | a cycle completes or a new target is added |
| `REVIEW.md` | Mavis (AI assistant) | one-time critique, re-audited quarterly |
| `PROFESSIONAL_AUDIT.md` | maintainer | pro tool landscape changes |
| `kawkab-ai-review.md` | Mavis (prior session) | archive only |
| `docs/INDEX.md` | this file | when a new doc is added |

---

## Adding a new doc

If you write a new markdown file in the repo:

1. Pick an existing category above (or propose a new one)
2. Add an entry to the "Quick links" section
3. Add an entry to the "Document authority" table
4. Add an entry to the "Source of truth" table
5. **Don't** write a doc that overlaps an existing one without first updating the index

> **Rule of thumb:** if you can't say who the audience is in one sentence, the doc isn't ready.
