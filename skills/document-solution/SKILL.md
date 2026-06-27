---
name: document-solution
description: >-
  Consolidates a Researcher<->Critic discussion into a single, self-contained,
  well-structured final document. Use when the Summarizer agent must observe a
  completed (or round-capped) debate and write the authoritative consolidated
  solution that the user receives and that could later be stored as knowledge.
metadata:
  version: "1.0"
  audience: summarizer
---

# Document the consolidated solution

You receive the full Researcher↔Critic transcript. Write the **final answer** the
user keeps. You are documenting an outcome, not adding new opinions.

## Rules

- **Synthesize, don't transcribe.** Merge the strongest proposal with the valid
  critiques into one coherent solution. Drop rejected dead-ends.
- **Be self-contained.** A reader who never saw the debate should fully
  understand the solution. Avoid "as Toni said" style references.
- **Be honest about residue.** If the loop ended on the round cap rather than
  agreement, state the remaining open points plainly under *Caveats*.

## Structure

```
# <Topic>

## Recommendation
<the agreed solution, stated decisively>

## Key decisions & rationale
<why this approach, with the trade-offs that were accepted>

## Steps / details
<concrete, actionable detail>

## Caveats & open questions
<anything unresolved, or "none">
```

Keep it tight and skimmable — headings, short paragraphs, and lists over walls of
text.
