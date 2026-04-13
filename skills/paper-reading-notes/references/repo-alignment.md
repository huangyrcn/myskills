# Repo Alignment Guide

How to map paper concepts to repository implementation when writing the Code Alignment section.

## Prerequisites

Before writing Code Alignment, check:

```yaml
# metadata.yaml
repo_search:
  selected:
    confidence: "high"  # or "medium", "low", "none"
    url: "https://github.com/owner/repo"
    type: "official"    # or "community"
```

If `confidence` is `none` or `null`, skip Code Alignment section entirely.

## Alignment Process

### Step 1: Identify Paper Components

From `paper.md`, extract:

| Component | What to look for |
|-----------|------------------|
| **Architecture** | Model class names, layer types, dimensions |
| **Loss functions** | Equations, loss terms, training objectives |
| **Data pipeline** | Input format, preprocessing steps, datasets |
| **Training** | Optimizer, learning rate, batch size, epochs |
| **Evaluation** | Metrics, benchmarks, test procedures |

### Step 2: Map to Repo Structure

Clone or read repo, match components:

```bash
# Typical repo structure
repo/
├── model.py         # Architecture definition
├── layers.py        # Custom layers
├── loss.py          # Loss functions
├── data.py          # Data loading/preprocessing
├── train.py         # Training loop
├── eval.py          # Evaluation
└── configs/         # Hyperparameters
```

### Step 3: Create Alignment Table

```markdown
## Code Alignment

Repository: https://github.com/owner/repo
Confidence: high (official)

| Paper Concept | Repo Location | Notes |
|---------------|---------------|-------|
| Graph Attention Layer | `layers.py:GATLayer` | Eq. 1-3 |
| Multi-head attention | `layers.py:MultiHeadGAT` | Section 3.2 |
| Loss function | `loss.py:contrastive_loss` | Eq. 5 |
| Dataset loader | `data.py:load_cora` | Cora benchmark |
| Training config | `configs/cora.yaml` | Table 2 hyperparams |
```

## Uncertainty Markers

When alignment is uncertain:

| Confidence | Marker |
|------------|--------|
| `medium` | Add "⚠️ Partial alignment" note |
| `low` | Add "⚠️ Alignment unreliable" note |
| Multiple candidates | List all, note which is most likely |

Example:

```markdown
## Code Alignment

> ⚠️ Repo confidence: medium (community reimplementation)

Repository: https://github.com/user/repo

Based on README and code structure:

| Paper Concept | Likely Location | Notes |
|---------------|-----------------|-------|
| Core model | `model.py` | Matches paper architecture |
| Loss function | `train.py:loss_fn` | Not in separate file |
| Preprocessing | Unknown | Not clearly documented |
```

## Common Patterns

### PyTorch Geometric repos

```
model.py          → model class
model/            → model modules (large repos)
layers/           → custom GNN layers
data.py           → dataset classes
train.py          → training script
utils.py          → helper functions
```

### Official vs Community differences

| Aspect | Official repo | Community repo |
|--------|---------------|----------------|
| Structure | Matches paper sections exactly | May differ from paper |
| Documentation | Paper section references | Generic docs |
| Configs | Exact hyperparameters from paper | Approximate values |
| Datasets | Paper benchmark scripts | Subset or different datasets |

## When to Skip Alignment

- `repo_search.selected.confidence` is `none` or `null`
- Repo is clearly unrelated (different domain)
- Repo is a fork without code changes
- Repo is empty or placeholder

In these cases, write:

```markdown
## Code Alignment

No reliable repository found. See `metadata.yaml` → `repo_search` for search attempts.
```
