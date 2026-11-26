"""Pair file format and integrity checks.

A pairs file is a tab-separated text file with one minimal pair per row.
Quote characters are not special, so sentences can contain quotation marks.
"""

from __future__ import annotations

import csv
import difflib
import unicodedata
from collections import Counter
from dataclasses import dataclass

PHENOMENA = {
    "neg_choice": "Negator choice",
    "svc": "Serial verb constructions",
    "wh_focus": "Wh-questions and focus",
    "cond": "Conditionals",
    "comp_type": "Complement clause type (pé vs kí)",
    "copula": "Copula choice",
    "npi": "NPI licensing",
    "tam_order": "TAM marker order",
    "obj_pron": "Third-person object pronoun",
}

COLUMNS = ["id", "phenomenon", "paradigm", "good", "bad", "edit", "source", "status", "notes"]
REQUIRED = ["id", "phenomenon", "good", "bad"]
STATUSES = {"draft", "validated", "rejected"}

_TONE_MARKS = {"\u0300", "\u0301", "\u0304"}


@dataclass
class Pair:
    id: str
    phenomenon: str
    good: str
    bad: str
    paradigm: str = ""  # sub-type within a phenomenon
    edit: str = ""  # the one change between good and bad, in words
    source: str = ""  # e.g. author, template, corpus
    status: str = "draft"  # draft, validated or rejected
    notes: str = ""


def load_pairs(path: str) -> list[Pair]:
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"pairs file is missing columns: {missing}")
        pairs = []
        for row in reader:
            if not (row.get("id") or "").strip():
                continue
            values = {c: (row.get(c) or "").strip() for c in COLUMNS}
            values["status"] = values["status"] or "draft"
            pairs.append(Pair(**values))
    return pairs


def write_pairs(path: str, pairs: list[Pair]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None, lineterminator="\n"
        )
        writer.writeheader()
        for p in pairs:
            writer.writerow({c: getattr(p, c) for c in COLUMNS})


def _odd_chars(s: str) -> set[str]:
    odd = set()
    for ch in s:
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            if not unicodedata.name(ch, "").startswith("LATIN"):
                odd.add(ch)
        elif cat.startswith(("M", "P", "N")) or cat == "Zs":
            continue
        else:
            odd.add(ch)
    return odd


def _has_tone_marks(s: str) -> bool:
    return any(ch in _TONE_MARKS for ch in unicodedata.normalize("NFD", s))


def changed_words(a: str, b: str) -> int:
    """Number of word positions that differ between two sentences."""
    wa, wb = a.split(), b.split()
    total = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=wa, b=wb, autojunk=False).get_opcodes():
        if tag != "equal":
            total += max(i2 - i1, j2 - j1)
    return total


def check_pairs(pairs: list[Pair]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors must be fixed; warnings need a look."""
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    seen_texts: set[tuple[str, str]] = set()

    for p in pairs:
        tag = p.id or "<no id>"
        if p.id in seen_ids:
            errors.append(f"{tag}: duplicate id")
        seen_ids.add(p.id)
        if p.phenomenon not in PHENOMENA:
            errors.append(f"{tag}: unknown phenomenon '{p.phenomenon}'")
        if p.status not in STATUSES:
            errors.append(f"{tag}: status must be one of {sorted(STATUSES)}")

        usable = True
        for name in ("good", "bad"):
            s = getattr(p, name)
            if not s.strip():
                errors.append(f"{tag}: {name} is empty")
                usable = False
                continue
            if "\t" in s or "\n" in s:
                errors.append(f"{tag}: {name} contains a tab or newline")
            if s != unicodedata.normalize("NFC", s):
                errors.append(f"{tag}: {name} is not NFC-normalised")
            if s != s.strip() or "  " in s:
                warnings.append(f"{tag}: {name} has stray whitespace")
            odd = _odd_chars(s)
            if odd:
                warnings.append(f"{tag}: {name} has unexpected characters {sorted(odd)}")
            if len(s.split()) >= 3 and not _has_tone_marks(s):
                warnings.append(f"{tag}: {name} has no tone marks; check it is fully marked")

        if not usable:
            continue
        if p.good.strip() == p.bad.strip():
            errors.append(f"{tag}: good and bad are identical")
            continue
        key = (p.good.strip(), p.bad.strip())
        if key in seen_texts:
            warnings.append(f"{tag}: same sentence pair appears more than once")
        seen_texts.add(key)
        n = changed_words(p.good, p.bad)
        if n > 2:
            warnings.append(f"{tag}: {n} words differ; is this still a minimal pair?")
    return errors, warnings


def summary(pairs: list[Pair]) -> dict[str, Counter]:
    """Counts per phenomenon, split by status."""
    out: dict[str, Counter] = {k: Counter() for k in PHENOMENA}
    for p in pairs:
        out.setdefault(p.phenomenon, Counter())[p.status] += 1
    return out
