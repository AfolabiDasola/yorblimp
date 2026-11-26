"""Tests. Run with `pytest`, or `python tests/test_yorblimp.py` if pytest is not installed.

The sentences below are placeholders to exercise the code. They are not
Yorùbá data and say nothing about the benchmark.
"""

import os
import tempfile
import unicodedata

from yorblimp.schema import Pair, changed_words, check_pairs, load_pairs, write_pairs
from yorblimp.score import bootstrap_ci, score_pairs, summarise
from yorblimp.validation import agreement, apply_status, fleiss_kappa, make_sheet


def pair(i, good="a b c", bad="a b", phen="wh_focus", status="draft"):
    return Pair(id=f"p{i}", phenomenon=phen, good=good, bad=bad, status=status)


# ------------------------------------------------------------------ schema --


def test_clean_pair_has_no_errors():
    errors, _ = check_pairs([pair(1)])
    assert errors == []


def test_identical_sentences_are_an_error():
    errors, _ = check_pairs([pair(1, good="a b c", bad="a b c")])
    assert any("identical" in e for e in errors)


def test_duplicate_id_and_bad_phenomenon():
    errors, _ = check_pairs([pair(1), pair(1), pair(2, phen="nonsense")])
    assert any("duplicate id" in e for e in errors)
    assert any("unknown phenomenon" in e for e in errors)


def test_non_nfc_is_an_error():
    decomposed = unicodedata.normalize("NFD", "\u1eb9 b c")
    errors, _ = check_pairs([pair(1, good=decomposed)])
    assert any("NFC" in e for e in errors)


def test_changed_words_counts_positions():
    assert changed_words("a b c", "a b") == 1
    assert changed_words("a b c", "a x c") == 1
    assert changed_words("a b c d", "w x y z") == 4


def test_many_changes_trigger_a_warning():
    _, warnings = check_pairs([pair(1, good="a b c d e", bad="v w x y z")])
    assert any("minimal pair" in w for w in warnings)


def test_round_trip_through_file():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "pairs.tsv")
        pairs = [pair(1, good='he said "a b c"'), pair(2)]
        write_pairs(path, pairs)
        assert load_pairs(path) == pairs


# ------------------------------------------------------------------- score --


def length_scorer(text):
    # shorter sentence gets the higher log-probability
    return -float(len(text)), len(text.split())


def test_scoring_and_summary():
    pairs = [pair(1), pair(2), pair(3, good="x y z", bad="x y z w", phen="svc")]
    items = score_pairs(pairs, length_scorer)
    result = summarise(items, n_boot=200)
    # in pairs 1 and 2 the bad sentence is shorter, so the scorer picks it
    assert result["phenomena"]["wh_focus"]["acc_sum"] == 0.0
    assert result["phenomena"]["svc"]["acc_sum"] == 1.0
    assert result["micro"]["n"] == 3
    assert result["macro_acc_sum"] == 0.5


def test_token_matched_subset():
    pairs = [pair(1, good="a b c", bad="a b d")]  # same token count
    items = score_pairs(pairs, length_scorer)
    stats = summarise(items, n_boot=50)["micro"]
    assert stats["n_token_matched"] == 1


def test_bootstrap_interval_is_sane():
    assert bootstrap_ci([True] * 20, n_boot=100) == (1.0, 1.0)
    lo, hi = bootstrap_ci([True] * 10 + [False] * 10, n_boot=500)
    assert 0.2 < lo < 0.5 < hi < 0.8
    assert bootstrap_ci([]) == (None, None)


# -------------------------------------------------------------- validation --


def test_fleiss_kappa_extremes():
    perfect = [{"good": 3}, {"bad": 3}, {"good": 3}, {"bad": 3}]
    assert abs(fleiss_kappa(perfect) - 1.0) < 1e-9
    # three raters split in every possible way, no better than chance
    chancy = [{"good": 2, "bad": 1}, {"good": 1, "bad": 2}, {"good": 2, "bad": 1}, {"good": 1, "bad": 2}]
    assert fleiss_kappa(chancy) < 0.1


def _fill_sheet(sheet_path, key_rows, out_path, intended_good_for):
    """Write a completed sheet where the rater picks the intended-good sentence for chosen pairs."""
    import csv

    with open(sheet_path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))
    for r in rows:
        pid, a_is = key_rows[r["item"]]
        picks_good = pid in intended_good_for
        if picks_good:
            r["judgment"] = "A" if a_is == "good" else "B"
        else:
            r["judgment"] = "B" if a_is == "good" else "A"
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", quoting=csv.QUOTE_NONE,
                           quotechar=None, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_sheet_key_and_agreement_end_to_end():
    import csv

    with tempfile.TemporaryDirectory() as d:
        pairs = [pair(i, good=f"g{i} x y", bad=f"b{i} x y") for i in range(1, 5)]
        pairs_path = os.path.join(d, "pairs.tsv")
        write_pairs(pairs_path, pairs)
        sheet, key = os.path.join(d, "sheet.tsv"), os.path.join(d, "key.tsv")
        assert make_sheet(pairs, sheet, key, seed=3) == 4

        with open(key, encoding="utf-8", newline="") as fh:
            key_rows = {r["item"]: (r["pair_id"], r["A_is"]) for r in csv.DictReader(fh, delimiter="\t")}

        # three raters: all agree with the author on p1-p3; on p4 only one of three does
        paths = []
        for n, agree_p4 in enumerate([True, False, False]):
            good_for = {"p1", "p2", "p3"} | ({"p4"} if agree_p4 else set())
            out = os.path.join(d, f"rater{n}.tsv")
            _fill_sheet(sheet, key_rows, out, good_for)
            paths.append(out)

        result = agreement(paths, key)
        assert result["n_pairs_rated"] == 4
        assert result["pairs"]["p1"]["passes"] and not result["pairs"]["p4"]["passes"]
        assert result["n_pass"] == 3
        assert result["fleiss_kappa"] is not None

        apply_status(pairs_path, result)
        statuses = {p.id: p.status for p in load_pairs(pairs_path)}
        assert statuses == {"p1": "validated", "p2": "validated", "p3": "validated", "p4": "rejected"}


def test_sheet_hides_the_intended_answer():
    with tempfile.TemporaryDirectory() as d:
        pairs = [pair(i, good=f"g{i} x y", bad=f"b{i} x y") for i in range(1, 41)]
        sheet, key = os.path.join(d, "s.tsv"), os.path.join(d, "k.tsv")
        make_sheet(pairs, sheet, key, seed=1)
        text = open(sheet, encoding="utf-8").read()
        # the good sentence should land in position A for roughly half the items
        a_good = sum(1 for line in text.splitlines()[1:] if line.split("\t")[1].startswith("g"))
        assert 10 < a_good < 30


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(exc))
    raise SystemExit(1 if failed else 0)
