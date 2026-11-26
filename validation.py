"""Native-speaker validation: rater sheets and agreement.

Raters see two sentences, A and B, in shuffled order with no hint of which
one the author intended as acceptable, and choose one of:

    A, B   that sentence is acceptable and the other is not
    both   both are acceptable
    neither  neither is acceptable

Judgments are mapped back to the author's intent with a key file that
raters never see:

    good     the rater picked the sentence the author marked acceptable
    bad      the rater picked the other one
    both / neither   as given
"""

from __future__ import annotations

import csv
import random
from collections import Counter

from .schema import Pair, load_pairs, write_pairs

CATEGORIES = ["good", "bad", "both", "neither"]
VALID_JUDGMENTS = {"a", "b", "both", "neither"}


def _write_tsv(path: str, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=fieldnames, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)


def _read_tsv(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))


def make_sheet(pairs: list[Pair], sheet_path: str, key_path: str, seed: int = 0, status: str = "draft") -> int:
    """Write a rater sheet and a private key for pairs with the given status."""
    rng = random.Random(seed)
    chosen = [p for p in pairs if p.status == status]
    rng.shuffle(chosen)
    sheet_rows, key_rows = [], []
    for n, p in enumerate(chosen, 1):
        item = f"item{n:04d}"
        good_first = rng.random() < 0.5
        a, b = (p.good, p.bad) if good_first else (p.bad, p.good)
        sheet_rows.append({"item": item, "sentence_A": a, "sentence_B": b, "judgment": "", "comment": ""})
        key_rows.append({"item": item, "pair_id": p.id, "A_is": "good" if good_first else "bad"})
    _write_tsv(sheet_path, ["item", "sentence_A", "sentence_B", "judgment", "comment"], sheet_rows)
    _write_tsv(key_path, ["item", "pair_id", "A_is"], key_rows)
    return len(chosen)


def read_rater_sheet(path: str) -> dict[str, str]:
    judgments = {}
    for row in _read_tsv(path):
        raw = (row.get("judgment") or "").strip().lower()
        if not raw:
            continue
        if raw not in VALID_JUDGMENTS:
            raise ValueError(f"{path}: '{row.get('judgment')}' for {row['item']} is not A, B, both or neither")
        judgments[row["item"]] = raw
    return judgments


def fleiss_kappa(table: list[dict]) -> float:
    """Fleiss' kappa. Each row maps category -> number of raters; all rows need the same total."""
    n_items = len(table)
    n = sum(table[0].values())
    if n_items == 0 or n < 2:
        raise ValueError("need at least one item and two raters")
    cats = sorted({c for row in table for c in row})
    p_j = [sum(row.get(c, 0) for row in table) / (n_items * n) for c in cats]
    p_i = [(sum(v * v for v in row.values()) - n) / (n * (n - 1)) for row in table]
    p_bar = sum(p_i) / n_items
    p_e = sum(p * p for p in p_j)
    return 1.0 if p_e >= 1 else (p_bar - p_e) / (1 - p_e)


def agreement(rater_paths: list[str], key_path: str, threshold: float = 2 / 3) -> dict:
    """Per-pair verdicts and overall agreement across raters."""
    key = {r["item"]: r for r in _read_tsv(key_path)}
    sheets = [read_rater_sheet(p) for p in rater_paths]

    labels: dict[str, list[str]] = {}
    for sheet in sheets:
        for item, j in sheet.items():
            if item not in key:
                raise ValueError(f"item {item} is not in the key file")
            if j in ("both", "neither"):
                label = j
            else:
                picked_good = (j == "a") == (key[item]["A_is"] == "good")
                label = "good" if picked_good else "bad"
            labels.setdefault(item, []).append(label)

    pairs = {}
    for item, got in labels.items():
        share = got.count("good") / len(got)
        pairs[key[item]["pair_id"]] = {
            "n_raters": len(got),
            "share_good": share,
            "labels": dict(Counter(got)),
            "passes": share >= threshold - 1e-9,
        }

    full = [Counter(got) for got in labels.values() if len(got) == len(rater_paths)]
    kappa = fleiss_kappa([dict(c) for c in full]) if full and len(rater_paths) >= 2 else None
    return {
        "pairs": pairs,
        "n_pairs_rated": len(pairs),
        "n_pass": sum(v["passes"] for v in pairs.values()),
        "fleiss_kappa": kappa,
        "n_items_rated_by_all": len(full),
        "threshold": threshold,
    }


def apply_status(pairs_path: str, result: dict) -> None:
    """Mark pairs validated or rejected in the pairs file."""
    pairs = load_pairs(pairs_path)
    for p in pairs:
        verdict = result["pairs"].get(p.id)
        if verdict is not None:
            p.status = "validated" if verdict["passes"] else "rejected"
    write_pairs(pairs_path, pairs)
