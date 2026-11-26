# Paradigm notes

Working notes for each phenomenon: what the contrast is, what changes between the two sentences, and where pairs tend to go wrong. These are a starting point for the author to revise, not a verified description of Yorùbá grammar. Add sub-paradigms in the `paradigm` column of the pairs file.

## General rules for every pair

1. **One change.** The two sentences differ in one controlled property. Record it in the `edit` column.
2. **Unacceptable on every reading.** The bad sentence must have no acceptable interpretation in any context. If a swap produces a different valid sentence with a different meaning, it is not a grammaticality pair.
3. **No context needed.** Raters see two sentences with no discourse around them. If a pair only works in a given context, rewrite it or drop it.
4. **Fully tone-marked and subdotted**, in NFC. Run `python -m yorblimp check` before anything else.
5. **Same words where possible.** Keep the lexical items identical across the pair so frequency does not decide the score. Where the contrast needs a word added or removed, note it in `edit`.
6. **Vary the content.** Rotate verbs, nouns, names and tenses across a paradigm so a model cannot win by memorising one frame.
7. **Aim for 30 to 50 pairs per phenomenon** before validation, and expect to lose some.

## Phenomena

### neg_choice: Negator choice
**Contrast:** the negator that suits the clause type, against one that does not (for example kò, má, kì í, kò tíì).
**Change:** the negator only.
**Watch for:** negators often differ in meaning and clause type, so a swap can give a different valid sentence. Fix the clause type for each pair (declarative, imperative, habitual, and so on) and test that the bad member is unacceptable for that clause type under any reading.

### svc: Serial verb constructions
**Contrast:** an acceptable serial verb construction against a version that breaks a constraint on it, such as argument sharing or tense and polarity marking across the verbs.
**Change:** the property that breaks the constraint, and nothing else.
**Watch for:** two verbs with a repeated subject can be a valid sequence of clauses rather than a serial construction. The bad member must be unacceptable, not merely a different structure.

### wh_focus: Wh-questions and focus
**Contrast:** a wh-phrase or focused phrase with the focus marker, against one without it or with it misplaced.
**Change:** presence or position of the marker.
**Watch for:** full and contracted forms of the marker both occur. Use the same form on both sides of a pair, and vary which form is used across pairs.

### cond: Conditionals
**Contrast:** a conditional with its full marking, against one with a required part missing.
**Change:** drop or move one part.
**Watch for:** some bare forms may be acceptable with a temporal or other reading. Check the bad member has no such reading.

### comp_type: Complement clause type (pé vs kí)
**Contrast:** the complementiser that the matrix verb selects, against the other one.
**Change:** the complementiser only.
**Watch for:** some verbs take both, with a change in meaning. Use verbs that take one only, and record the verb class in `paradigm`.

### copula: Copula choice
**Contrast:** the copula suited to identity, predication or location, against an unsuited one.
**Change:** the copula only.
**Watch for:** ni also marks focus, so a bad sentence with ni may be acceptable as a focus construction. Avoid frames with that reading.

### npi: NPI licensing
**Contrast:** an NPI in a context that licenses it, against one that does not.
**Change:** the licensing context, for example negation present or absent.
**Watch for:** free-choice readings. The bad member must have no acceptable reading.

### tam_order: TAM marker order
**Contrast:** markers in an acceptable order or combination, against an unacceptable one.
**Change:** order or choice of markers.
**Watch for:** register and dialect variation, and contraction. Where speakers vary, treat the pair as a candidate for the validation step rather than assuming it.

### obj_pron: Third-person object pronoun
**Contrast:** the object pronoun form that suits the verb, against a wrong form.
**Change:** the pronoun only.
**Watch for:** the form depends on the verb's final vowel and tone, and spelling conventions differ (separate or joined). Fix one convention and state it in the README.

## Planned analyses (once pairs are validated)

- Accuracy per phenomenon with confidence intervals, for several multilingual causal and masked models.
- The token-matched subset reported separately, to separate length effects from grammar.
- Error analysis by `paradigm`, to see which constraints models miss.
- Rater agreement (Fleiss' kappa) and the share of pairs that survive validation.
