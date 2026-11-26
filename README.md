# yorblimp

A benchmark of grammatical minimal pairs for Yorùbá, and the tools to build, validate and score it.

**Status:** under construction. The tooling is in place; the pairs file is empty until the data is written and validated.

## Why

BLiMP-style benchmarks test whether a language model prefers the acceptable member of a minimal pair. [BLiMP](https://github.com/alexwarstadt/blimp) does this for English. MultiBLiMP covers 101 languages with pairs built automatically from Universal Dependencies and UniMorph, but only tests subject-verb agreement, which says little about a language with little agreement morphology like Yorùbá. This project covers constructions that are distinctive for Yorùbá and written by hand.

## Phenomena in the first release

| id | phenomenon |
|---|---|
| `neg_choice` | Negator choice |
| `svc` | Serial verb constructions |
| `wh_focus` | Wh-questions and focus |
| `cond` | Conditionals |
| `comp_type` | Complement clause type (pé vs kí) |
| `copula` | Copula choice |
| `npi` | NPI licensing |
| `tam_order` | TAM marker order |
| `obj_pron` | Third-person object pronoun |

What each contrast is, what changes, and the usual pitfalls are in [docs/paradigms.md](docs/paradigms.md).

## Data format

`data/pairs.tsv`, tab-separated, one pair per row:

| column | meaning |
|---|---|
| `id` | unique id |
| `phenomenon` | one of the ids above |
| `paradigm` | sub-type within the phenomenon |
| `good` | the acceptable sentence |
| `bad` | the unacceptable sentence |
| `edit` | the one change between them, in words |
| `source` | how it was produced (author, template, corpus) |
| `status` | `draft`, `validated` or `rejected` |
| `notes` | anything a reviewer should know |

All text is NFC-normalised and fully tone-marked. `data/format_example.tsv` shows the layout; its rows are placeholders, not data.

## Workflow

```
pip install -e .                       # add ".[score]" for model scoring

python -m yorblimp check data/pairs.tsv
python -m yorblimp make-sheet data/pairs.tsv --sheet rater_sheet.tsv --key sheet_key.tsv
# send rater_sheet.tsv to each rater, keep sheet_key.tsv private
python -m yorblimp agreement --key sheet_key.tsv --raters r1.tsv r2.tsv r3.tsv --apply data/pairs.tsv
python -m yorblimp score --model <model-name> --type causal
```

1. **check** catches empty or duplicate rows, non-NFC text, missing tone marks, identical sentences, and pairs that differ in more than two words.
2. **make-sheet** shuffles the pairs and randomises which sentence appears as A or B. Raters choose `A`, `B`, `both` or `neither` for each item, without context.
3. **agreement** maps their answers back to the author's intent, reports Fleiss' kappa, and lists pairs where fewer than two thirds of raters chose the intended sentence. With `--apply` it marks pairs `validated` or `rejected`.
4. **score** runs only validated pairs by default.

## Scoring

A pair is correct when the model scores the acceptable sentence higher. Because the two sentences often differ in length, two scores are reported:

- **sum**: total log-probability of the sentence
- **mean**: total log-probability divided by the number of tokens

Pairs whose sentences have the same token count are also reported separately, since there length cannot explain a result. Accuracy comes with 95% bootstrap intervals over pairs, per phenomenon, plus micro and macro averages.

Causal models are scored by log-probability. Masked models are scored by pseudo-log-likelihood, which favours multi-token words, so treat masked and causal results as separate columns rather than one ranking. Per-pair results are written to `results/` for error analysis.

## Limitations

- Tokenisation of subdotted letters and tone marks differs between models and affects raw probabilities. The token-matched subset and the mean score are there to make this visible, not to remove it.
- Acceptability judgments in Yorùbá vary by dialect and register. Rater agreement is reported rather than assumed, and rater background should be documented with the release.
- Hand-written pairs are fewer than automatically generated ones, so confidence intervals will be wider than in large benchmarks.

## Tests

```
pip install -e ".[dev]"
pytest
```

## Licence

Code: MIT (see LICENSE). A licence for the data will be added when the pairs are released.
