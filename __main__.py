"""Command line: python -m yorblimp {check,make-sheet,agreement,score} ..."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from .schema import PHENOMENA, check_pairs, load_pairs, summary


def cmd_check(args) -> int:
    pairs = load_pairs(args.pairs)
    errors, warnings = check_pairs(pairs)
    for msg in errors:
        print("error:  ", msg)
    for msg in warnings:
        print("warning:", msg)
    print(f"\n{len(pairs)} pairs, {len(errors)} errors, {len(warnings)} warnings")
    print(f"{'phenomenon':<34}{'draft':>7}{'valid.':>8}{'reject.':>9}")
    for phen, counts in summary(pairs).items():
        print(f"{PHENOMENA.get(phen, phen):<34}{counts['draft']:>7}{counts['validated']:>8}{counts['rejected']:>9}")
    return 1 if errors else 0


def cmd_make_sheet(args) -> int:
    from .validation import make_sheet

    n = make_sheet(load_pairs(args.pairs), args.sheet, args.key, seed=args.seed, status=args.status)
    print(f"wrote {n} items to {args.sheet}; keep {args.key} private")
    return 0


def cmd_agreement(args) -> int:
    from .validation import agreement, apply_status

    result = agreement(args.raters, args.key, threshold=args.threshold)
    kappa = result["fleiss_kappa"]
    print(f"pairs rated: {result['n_pairs_rated']}, passing: {result['n_pass']}")
    print(f"Fleiss' kappa: {'n/a' if kappa is None else f'{kappa:.3f}'} "
          f"({result['n_items_rated_by_all']} items rated by every rater)")
    for pid, v in sorted(result["pairs"].items()):
        if not v["passes"]:
            print(f"  fails: {pid}  share good={v['share_good']:.2f}  labels={v['labels']}")
    if args.apply:
        apply_status(args.apply, result)
        print(f"updated statuses in {args.apply}")
    return 0


def cmd_score(args) -> int:
    from .score import CausalScorer, MaskedScorer, score_pairs, summarise

    pairs = load_pairs(args.pairs)
    if args.status != "all":
        pairs = [p for p in pairs if p.status == args.status]
    if not pairs:
        print(f"no pairs with status '{args.status}'", file=sys.stderr)
        return 1
    scorer_cls = CausalScorer if args.type == "causal" else MaskedScorer
    scorer = scorer_cls(args.model, device=args.device)
    items = score_pairs(pairs, scorer)
    result = summarise(items)
    result["model"] = args.model
    result["scoring"] = args.type

    os.makedirs(args.out_dir, exist_ok=True)
    stem = args.model.replace("/", "__")
    with open(os.path.join(args.out_dir, f"{stem}.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out_dir, f"{stem}.items.tsv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["id", "phenomenon", "lp_good", "lp_bad", "n_good", "n_bad", "correct_sum", "correct_mean"])
        for it in items:
            w.writerow([it.id, it.phenomenon, f"{it.lp_good:.4f}", f"{it.lp_bad:.4f}", it.n_good, it.n_bad,
                        int(it.correct_sum), int(it.correct_mean)])
    print(f"{'phenomenon':<34}{'n':>5}{'acc(sum)':>10}{'acc(mean)':>11}")
    for phen, v in result["phenomena"].items():
        print(f"{PHENOMENA[phen]:<34}{v['n']:>5}{v['acc_sum']:>10.3f}{v['acc_mean']:>11.3f}")
    print(f"{'macro average':<34}{'':>5}{result['macro_acc_sum']:>10.3f}{result['macro_acc_mean']:>11.3f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yorblimp", description="Yorùbá minimal-pair benchmark tools.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", help="check a pairs file")
    p.add_argument("pairs")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("make-sheet", help="build a rater sheet and private key")
    p.add_argument("pairs")
    p.add_argument("--sheet", default="rater_sheet.tsv")
    p.add_argument("--key", default="sheet_key.tsv")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--status", default="draft", help="which pairs to include (default: draft)")
    p.set_defaults(fn=cmd_make_sheet)

    p = sub.add_parser("agreement", help="agreement across completed rater sheets")
    p.add_argument("--key", required=True)
    p.add_argument("--raters", nargs="+", required=True, help="one completed sheet per rater")
    p.add_argument("--threshold", type=float, default=2 / 3, help="share of raters who must pick the intended sentence")
    p.add_argument("--apply", metavar="PAIRS", help="write validated/rejected into this pairs file")
    p.set_defaults(fn=cmd_agreement)

    p = sub.add_parser("score", help="score pairs with a language model")
    p.add_argument("--model", required=True)
    p.add_argument("--type", choices=["causal", "masked"], default="causal")
    p.add_argument("--pairs", default="data/pairs.tsv")
    p.add_argument("--status", default="validated", help="'validated' (default), 'draft', or 'all'")
    p.add_argument("--out-dir", default="results")
    p.add_argument("--device")
    p.set_defaults(fn=cmd_score)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
