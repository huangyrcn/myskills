# Source Normalization Policy

The acquisition stage always tries to produce:

```text
paper/paper.md
```

## Backend Order

### Preferred backend: LaTeX -> Pandoc

Use this path when:

- `main.tex` or another plausible main TeX file exists
- Pandoc can render a meaningful markdown body

Recommended reader/writer settings:

```text
pandoc -f latex+raw_tex -t markdown+tex_math_dollars
```

Rationale:

- better section structure
- better math preservation
- better citation preservation
- avoids OCR/layout noise

### Fallback backend: PDF -> MinerU

Use this path when:

- no usable LaTeX exists
- Pandoc fails
- the LaTeX conversion is obviously incomplete

## Quality Gate

Fall back to PDF normalization if the LaTeX conversion:

- produces an almost empty body
- loses the paper body structure
- fails on includes/macros badly enough that the text is unusable

Record the chosen backend in `metadata.yaml` under a normalization section.
