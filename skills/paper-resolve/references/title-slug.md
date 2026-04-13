# Title Slug Contract

`title_slug` is the stable filesystem identifier for the canonical raw bundle.

## Principles

- derive it from the **canonical paper title**, not the user's raw input
- keep it stable across projects
- use it only for raw bundle identity, not for note naming

## Base Slug Rule

Generate the base slug by:

1. Unicode normalize
2. transliterate to ASCII where possible
3. lowercase
4. replace non-alphanumeric runs with `_`
5. collapse repeated `_`
6. trim leading and trailing `_`
7. cap length

Example:

```text
Attention Is All You Need
-> attention_is_all_you_need
```

## Collision Rule

If the base slug already exists:

- reuse it if the existing bundle refers to the same paper
- otherwise add a stable suffix

Stable suffix priority:

1. arXiv id
2. DOI short hash
3. OpenReview/OpenAlex/Semantic Scholar id fragment

Examples:

```text
attention_is_all_you_need_1706_03762
paper_name_d3ab91f2
```
