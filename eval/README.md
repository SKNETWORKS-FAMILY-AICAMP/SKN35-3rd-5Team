# Preliminary judge evaluation

The team-authored golden set from `origin/lhm` is preserved: dev 45, holdout 21.
It is a project benchmark, not a collection of 66 official legal rulings.
Do not replace it with the earlier 3-line sample during integration.

Run from the project root:

```powershell
uv run python -m eval.run_eval --backend rule --split dev
uv run python -m eval.run_eval --backend gpt --split dev
uv run python -m eval.run_eval --backend gpt-few --split dev
uv run python -m eval.run_eval --backend rule gpt gpt-few --split dev
```

GPT evaluation uses the `.env` API key/model and incurs API charges.
Outputs are saved under `output/eval/` (Git ignored).
API/parse failures count as missed predictions and are reported separately.
The macro-F1 uses a fixed label set of 0/1/2. Failure cases contribute false negatives.
Holdout requires `--split holdout --allow-holdout`; reserve it for final evaluation.

These commands evaluate the standalone preliminary judge, not the RAG workflow,
retrieval citations, alternative copy, or final legal compliance.
Rule matching now includes expanded banned expressions, functional exceptions,
substantiation, comparisons, and numerical evidence checks. Its development-set
score does not establish performance on unseen cases or legal correctness.
Numerical checks require all numerical tokens in a sentence to be supported by
one evidence record for the same detected effect. Separate sentences can cite
separate records. Institution names are excluded from measured results.
The workflow's rule floor now uses the same product-aware evaluation, including
numerical contradictions and missing substantiation, before GPT judgment.
Limit: effect detection still uses keywords, and compound claims or multiple
time points inside one free-text evidence record require structured evidence.
Negation, evidence scope, and exceptions also require independent validation.
GPT receives product evidence but no golden-set answers or notes.
Prompt versions are `judge-zero-shot-v2` and `judge-few-shot-v2` (8 examples).
The example-overlap test checks exact normalized copy overlap, not semantic leakage.

The latest team graph/retrieval implementations have been integrated into kjh.
Full RAG evaluation still requires the shared Qdrant connection and an assessment
of whether retrieved evidence actually supports the claim, not only its presence.
