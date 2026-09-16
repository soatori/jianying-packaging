# Light display-content policy

Packaging may make display-only corrections after rough-cut approval:

- shorten on-screen wording without changing meaning;
- adjust line breaks and punctuation;
- select sentence, phrase, word, or character emphasis;
- define an overlay/coverage relationship;
- adjust display segmentation while preserving the spoken semantic unit.

The following belong to `jianying-rough-cut` and must be returned there:

- deleting a complete spoken unit;
- changing numbers, names, terms, conditions, causal relations, or conclusions;
- changing semantic order;
- removing fillers, repetitions, false starts, or pauses;
- correcting speech content rather than its display.

Every light operation records its target, before/after display text when relevant, `semantic_preserved=true`, and review status. A packaging validator must reject semantic deletion or reordering masquerading as a light operation.
