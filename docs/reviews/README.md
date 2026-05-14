# docs/reviews — multi-LLM review pack

Independent reviews of Forensa's docs and code, one per LLM. Each is the LLM's own honest assessment; nothing here is consensus or product team output.

## Folder layout

Reviews are organised into numbered subfolders, one per review:

```
docs/reviews/
  01_Rev_Claude_20260514_0919/
    EnterpriseGradeReview_Claude_20260514_0906.md
    REVIEW_RESPONSE_AND_BACKLOG_20260514_<HHMM>.md   (if a response was produced)
  02_Rev_<LLM>_<YYYYMMDD>_<HHMM>/
    ...
```

The folder number (`NN_Rev_...`) gives chronological order. The review file inside follows the naming convention below.

## Naming convention

`<ReviewType>_<LLM>_<YYYYMMDD>_<HHMM>.md`

- **ReviewType:** short PascalCase noun describing what was reviewed (e.g. `EnterpriseGradeReview`, `SecurityReview`, `BRDReview`, `CodeReview`)
- **LLM:** which model wrote it — `Claude`, `ChatGPT`, `Perplexity`, `Gemini`
- **Date + time:** when the review was authored, local timezone, 24h

Examples:

- `EnterpriseGradeReview_Claude_20260514_0906.md`
- `EnterpriseGradeReview_ChatGPT_20260514_1130.md`
- `SecurityReview_Perplexity_20260515_0900.md`

## Review log

| # | Folder / File | LLM | Date | Subject | Length | Notes |
|---:|---|---|---|---|---:|---|
| 01 | [01_Rev_Claude_20260514_0919/EnterpriseGradeReview_Claude_20260514_0906.md](01_Rev_Claude_20260514_0919/EnterpriseGradeReview_Claude_20260514_0906.md) | Claude | 14 May 2026 09:06 | Full docs + product + line-by-line code | ~63 KB | First review. Reading manifest at top declares exactly which files were read. Response + backlog mapping in the same folder. |

## Convention for adding a review

1. Create a new numbered subfolder: `NN_Rev_<LLM>_<YYYYMMDD>_<HHMM>/` where `NN` is the next integer.
2. Drop the review file inside using the naming convention above.
3. Add a row to the review log table above.
4. If your review references a specific code commit, include the short SHA in the file header.
5. Be explicit about what you **did and did not read**. A reading manifest at the top of the doc protects every reader from over-trusting an LLM's confidence on files it never opened.
6. If you flag a fix as urgent (e.g. "show-stopper before submission"), state your reasoning. Other reviewers may disagree; the disagreement is itself signal.
7. If the review prompts a response (action taken / backlog created), drop a `REVIEW_RESPONSE_AND_BACKLOG_<YYYYMMDD>_<HHMM>.md` alongside the review in the same subfolder.

## Reading order for a new reviewer / team member

1. Start with the most recent review (highest folder number).
2. Cross-reference against the Strategy phase docs in the parent project folder (`0007_AT_Hack0018_Forensa_TechEx_Veea_Google/docs/`) for context on why Forensa was chosen.
3. Treat each review as one LLM's lens, not as the answer. The point of having multiple LLMs review is the diff — where they agree is signal, where they disagree is signal too.
