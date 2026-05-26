# Blind Human Evaluation Tool

Open `index.html` in a browser and load:

```text
results/20260519_232753_writer_blind_human_eval.json
```

The tool samples the same 10 articles for every evaluator using a fixed seed and includes all 3 review items for each sampled article, for 30 total judgments.

## Evaluator Workflow

1. Enter an evaluator ID, such as `eval_01`.
2. Choose a preference for overall quality, factuality, and coverage on every item.
3. Use notes only when useful; notes are optional.
4. Use `Jump to incomplete` to find missing required fields.
5. Click `Finish / Export` and save the generated `human_eval_completed_<evaluator_id>.json`.

Progress is autosaved in browser localStorage. Refreshing or closing the tab should preserve the current sampled items and answers. Use `Reset` only when starting over for a new evaluator in the same browser.

## Preference Values

- `A`
- `B`
- `Tie`
- `Unsure`

## Analysis

After collecting the completed exports from all evaluators, run:

```bash
python human_eval_tool/analyze_results.py human_eval_completed_eval_*.json
```

The script joins completed blind outputs with `results/20260519_232753_writer_labeled_human_eval_key.json`, decodes `A` and `B` into `writer` and `ai`, and reports preference rates plus simple pairwise inter-rater agreement.
