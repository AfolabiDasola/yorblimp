"""Score minimal pairs with language models.

A pair counts as correct when the model gives the acceptable sentence a
higher score than the unacceptable one. Two scores are reported because the
two sentences often differ in length:

    sum  : total log-probability of the sentence
    mean : total log-probability divided by the number of tokens

Pairs whose sentences have the same token count are also reported on their
own, because there the two scores agree and length cannot explain the result.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from .schema import PHENOMENA, Pair

# A scorer maps a sentence to (total log-probability, number of scored tokens).
Scorer = Callable[[str], tuple[float, int]]


@dataclass
class ItemResult:
    id: str
    phenomenon: str
    lp_good: float
    lp_bad: float
    n_good: int
    n_bad: int

    @property
    def correct_sum(self) -> bool:
        return self.lp_good > self.lp_bad

    @property
    def correct_mean(self) -> bool:
        return self.lp_good / self.n_good > self.lp_bad / self.n_bad

    @property
    def token_matched(self) -> bool:
        return self.n_good == self.n_bad


def score_pairs(pairs: list[Pair], scorer: Scorer) -> list[ItemResult]:
    results = []
    for p in pairs:
        lp_g, n_g = scorer(p.good)
        lp_b, n_b = scorer(p.bad)
        results.append(ItemResult(p.id, p.phenomenon, lp_g, lp_b, n_g, n_b))
    return results


def bootstrap_ci(flags: list[bool], n_boot: int = 1000, seed: int = 0, alpha: float = 0.05):
    """Percentile bootstrap interval for an accuracy over pairs."""
    if not flags:
        return None, None
    rng = random.Random(seed)
    n = len(flags)
    values = [1 if f else 0 for f in flags]
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return lo, hi


def _group_stats(items: list[ItemResult], n_boot: int, seed: int) -> dict:
    n = len(items)
    sum_flags = [i.correct_sum for i in items]
    mean_flags = [i.correct_mean for i in items]
    matched = [i for i in items if i.token_matched]
    out = {
        "n": n,
        "acc_sum": sum(sum_flags) / n if n else None,
        "acc_sum_ci95": bootstrap_ci(sum_flags, n_boot, seed),
        "acc_mean": sum(mean_flags) / n if n else None,
        "acc_mean_ci95": bootstrap_ci(mean_flags, n_boot, seed),
        "n_token_matched": len(matched),
        "acc_token_matched": (sum(i.correct_sum for i in matched) / len(matched)) if matched else None,
    }
    return out


def summarise(items: list[ItemResult], n_boot: int = 1000, seed: int = 0) -> dict:
    """Per-phenomenon accuracy plus micro and macro averages."""
    by_phen: dict[str, list[ItemResult]] = {}
    for it in items:
        by_phen.setdefault(it.phenomenon, []).append(it)
    result = {"phenomena": {}}
    for phen in PHENOMENA:
        if phen in by_phen:
            result["phenomena"][phen] = _group_stats(by_phen[phen], n_boot, seed)
    result["micro"] = _group_stats(items, n_boot, seed)
    accs = [v["acc_sum"] for v in result["phenomena"].values() if v["acc_sum"] is not None]
    result["macro_acc_sum"] = sum(accs) / len(accs) if accs else None
    mean_accs = [v["acc_mean"] for v in result["phenomena"].values() if v["acc_mean"] is not None]
    result["macro_acc_mean"] = sum(mean_accs) / len(mean_accs) if mean_accs else None
    return result


# ---------------------------------------------------------------- scorers ---


class CausalScorer:
    """Log-probability under a causal LM (e.g. a BLOOM or Llama-style model)."""

    def __init__(self, model_name: str, device: str | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to(self.device).eval()
        tok = self.tokenizer
        self.start_id = tok.bos_token_id if tok.bos_token_id is not None else tok.eos_token_id

    def __call__(self, text: str) -> tuple[float, int]:
        torch = self.torch
        ids = self.tokenizer(text, add_special_tokens=False, return_tensors="pt").input_ids[0]
        inputs = torch.cat([torch.tensor([self.start_id]), ids]).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(inputs).logits[0, :-1]
        logprobs = torch.log_softmax(logits.float(), dim=-1)
        token_lp = logprobs.gather(1, inputs[0, 1:].unsqueeze(1)).squeeze(1)
        return token_lp.sum().item(), int(ids.numel())


class MaskedScorer:
    """Pseudo-log-likelihood under a masked LM (Salazar et al., 2020).

    Each token is masked in turn and its log-probability summed. This is the
    simple version; it is known to favour multi-token words, so treat results
    from masked and causal models as separate columns, not one ranking.
    """

    def __init__(self, model_name: str, device: str | None = None):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name).to(self.device).eval()

    def __call__(self, text: str) -> tuple[float, int]:
        torch = self.torch
        ids = self.tokenizer(text, return_tensors="pt").input_ids[0]
        special = set(self.tokenizer.all_special_ids)
        positions = [i for i, t in enumerate(ids.tolist()) if t not in special]
        batch = ids.repeat(len(positions), 1)
        for row, pos in enumerate(positions):
            batch[row, pos] = self.tokenizer.mask_token_id
        with torch.no_grad():
            logits = self.model(batch.to(self.device)).logits
        logprobs = torch.log_softmax(logits.float(), dim=-1)
        total = 0.0
        for row, pos in enumerate(positions):
            total += logprobs[row, pos, ids[pos]].item()
        return total, len(positions)
