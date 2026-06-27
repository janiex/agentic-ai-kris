---
name: web-research
description: >-
  Researches a topic by gathering, cross-checking, and synthesizing factual
  information from retrieved knowledge (RAG) and prior context. Use when the
  Researcher agent must investigate a user-assigned subject, establish the
  relevant facts, options, and trade-offs, and produce a grounded solution that
  cites where each claim comes from.
metadata:
  version: "1.0"
  audience: researcher
---

# Web / knowledge research

Produce a **grounded, well-structured solution** to the assigned topic.

## Method

1. **Frame the question.** Restate the task in one sentence and list the
   sub-questions you must answer to solve it.
2. **Gather evidence.** Use the retrieved knowledge passages provided in the
   prompt (labelled `[K1]`, `[K2]`, …). Treat them as your primary sources.
3. **Cross-check.** Where sources disagree or are silent, say so explicitly
   rather than guessing. Distinguish *established fact* from *your inference*.
4. **Synthesize.** Write a concrete proposed solution: the recommendation, the
   key decisions, the trade-offs, and any open risks.
5. **Cite.** Reference supporting passages inline as `[K1]`, `[K2]`. If a claim
   has no supporting passage, mark it `(unverified)`.

## Output shape

- **Summary** — 2–3 sentences answering the task directly.
- **Findings** — bulleted, each with its citation.
- **Proposed solution** — the actionable recommendation.
- **Open questions / risks** — what remains uncertain.

## When revising after a critique

Address each of the Critic's points explicitly: either fix the solution or
defend the original choice with reasoning. Do not silently drop a critique.

For a deeper checklist of source-quality heuristics, see `reference.md`. To
normalise a messy block of retrieved text into clean bullet points, you may run
the bundled helper `scripts/extract_claims.py`.
