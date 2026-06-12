"""Extractiveness analysis: extractive COVERAGE and DENSITY for each system's summaries against their source articles, on the shared
76-article writer set. Answers the paper's title question: are newer LLMs more/less
extractive than human writers (and than the older Instruct Davinci)?

Coverage = (1/|S|) * sum_f |f|       (fraction of summary tokens that are copied spans)
Density  = (1/|S|) * sum_f |f|^2     (avg. length of the copied span each token belongs to)
where F is the set of extractive fragments from the greedy matching in Grusky Alg. 1
"""
import json, re, csv
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
PAPER_DIR = next((p for p in [HERE.parent / "benchmark_llm_summarization-main",
                              HERE / "benchmark_llm_summarization-main"] if p.exists()), None)
if PAPER_DIR is None:
    raise SystemExit("Could not find benchmark_llm_summarization-main")

MODERN_OUTPUTS = HERE / "outputs" / "20260519_232753_writer_summaries_generations.jsonl"
WRITER_FILE = PAPER_DIR / "writer_summaries.json"
PAIRWISE_FILE = PAPER_DIR / "pairwise_evaluation_results.json"
OUT_FILE = HERE / "results" / "extractiveness_scores.csv"


def tokenize(text):
    return re.findall(r"\w+", (text or "").lower())


def extractive_fragments(article_tokens, summary_tokens):
    """Greedy fragment matching, Grusky et al. (2018) Algorithm 1."""
    A, S = article_tokens, summary_tokens
    fragments = []
    i = 0
    while i < len(S):
        best = []
        j = 0
        while j < len(A):
            if S[i] == A[j]:
                i_, j_ = i, j
                while i_ < len(S) and j_ < len(A) and S[i_] == A[j_]:
                    i_ += 1
                    j_ += 1
                if len(best) < (i_ - i):
                    best = S[i:i_]
                j = j_
            else:
                j += 1
        i += max(len(best), 1)
        if best:
            fragments.append(best)
    return fragments


def coverage_density(article, summary):
    A, S = tokenize(article), tokenize(summary)
    if not S:
        return None
    F = extractive_fragments(A, S)
    coverage = sum(len(f) for f in F) / len(S)
    density = sum(len(f) ** 2 for f in F) / len(S)
    return coverage, density


def main():
    rows = []

    # modern models
    modern = [json.loads(l) for l in open(MODERN_OUTPUTS)]
    subset_ids = {r["id"] for r in modern}         
    for r in modern:
        rows.append((r["model"], r["id"], r["article"], r["generated_summary"]))

    # freelance writers
    for w in json.load(open(WRITER_FILE)):
        if w["article_id"] in subset_ids:
            rows.append(("freelance_writer", w["article_id"], w["article"], w["summary"]))

    # Instruct Davinci
    seen = set()
    for x in json.load(open(PAIRWISE_FILE)):
        if x["article_id"] in subset_ids and x["article_id"] not in seen:
            seen.add(x["article_id"])
            rows.append(("text-davinci-002", x["article_id"], x["article_text"],
                         x["text-davinci-002_summary"]))

    # calc scores
    per_system = defaultdict(list)
    out_rows = []
    for system, aid, article, summary in rows:
        cd = coverage_density(article, summary)
        if cd is None:
            continue
        cov, den = cd
        per_system[system].append((cov, den))
        out_rows.append({"system": system, "id": aid,
                         "coverage": round(cov, 4), "density": round(den, 4)})

    with OUT_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["system", "id", "coverage", "density"])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Per-summary scores written to: {OUT_FILE}\n")
    order = ["freelance_writer", "text-davinci-002",
             "llama3.1:latest", "gemma2:9b", "gpt-4o-mini-2024-07-18"]
    print(f"{'System':24s} {'n':>4s}  {'Coverage':>9s}  {'Density':>8s}")
    for system in order:
        vals = per_system.get(system, [])
        if not vals:
            continue
        cov = sum(v[0] for v in vals) / len(vals)
        den = sum(v[1] for v in vals) / len(vals)
        print(f"{system:24s} {len(vals):4d}  {cov:9.4f}  {den:8.4f}")


if __name__ == "__main__":
    main()
