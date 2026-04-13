# Research-Style Reading Note Ontology

The note should reorganize the paper, not compress it.

## Required Sections

### 1. One-sentence summary

State:

- the key mechanism
- the problem it solves
- the most notable outcome

### 2. What problem does this paper really solve?

Reconstruct:

- task
- setting
- existing methods
- hidden assumptions
- assumption-setting mismatch
- problem statement
- why the problem matters

Do not turn this section into method introduction.

### 3. Core idea

Explain the central insight:

- what the author realized
- what conceptual shift the paper makes
- what bottleneck or bias is being changed

Do not collapse this section into a module list.

### 4. Method pipeline

Explain how the idea becomes a concrete system:

- architecture
- main modules
- objective or loss
- training path
- inference path

### 5. Real contributions

For each contribution, state:

- what prior work lacked
- what this paper newly adds
- why it is not just implementation detail

### 6. Hardest parts to understand

Highlight:

- non-obvious assumptions
- likely misunderstandings
- counterintuitive ideas

### 7. Code alignment

Map paper concepts to implementation:

- which file owns which conceptual part
- where the key training or forward path lives
- where paper and repo do not fully align

If there is no trustworthy repo, say so plainly.

### 8. Experimental evidence

Organize this section by claim, not by table.

For each major claim:

- claim
- evidence
- whether the evidence is strong enough

### 9. Limitations and reproduction risks

Separate:

- research limitations
- engineering or reproducibility risks

### 10. Reading path

Explain:

- what to read first
- which figures or tables carry the main logic
- what can be skipped on a first pass

## Guardrails

Never confuse:

- setting vs goal
- problem statement vs method
- core idea vs pipeline
- contributions vs module list
- experiment results vs evidence
- limitations vs polite criticism

## Quality Checks

Before finishing, verify:

1. Section 2 explains why the paper exists.
2. Section 3 does not collapse into Section 4.
3. Section 5 contains deltas against prior work, not repetition.
4. Section 8 ties evidence to claims.
5. Section 9 separates research limits from reproduction risks.
6. The note includes both the author's claims and the note writer's judgment.
