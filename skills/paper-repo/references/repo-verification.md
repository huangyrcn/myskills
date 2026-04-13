# Repo Verification Criteria

Detailed criteria for judging repository authenticity and alignment with paper.

## Official vs Community

| Type | Definition | Evidence |
|------|------------|----------|
| **official** | Authors or their team released | Author name match, README states "official implementation" |
| **community** | Third-party reimplementation | No author match, README cites paper but admits reimplementation |
| **fork** | Fork of official repo | Fork network points to official repo |
| **unrelated** | Name collision only | No paper connection, different domain |

## Evidence Checklist

### High confidence evidence

- [ ] README contains exact DOI from `identity.aliases.doi`
- [ ] README links to `urls.canonical` (arXiv/publisher)
- [ ] GitHub owner name matches `bibliography.authors`
- [ ] README explicitly states "official implementation"
- [ ] Paper PDF contains this repo URL (from extract_urls_from_pdf.py)

### Medium confidence evidence

- [ ] Repo name contains method name from title
- [ ] README mentions paper title
- [ ] Repo created within 1 year of paper publication
- [ ] Code structure matches paper methodology (e.g., model architecture)

### Low confidence evidence

- [ ] Only name similarity
- [ ] No README citation
- [ ] Different domain/topic
- [ ] Repo created much later than paper

## Author Name Matching

Match GitHub owner/display name against `bibliography.authors`:

```yaml
# metadata.yaml
bibliography:
  authors:
    - "Hongbin Pei"
    - "Bingzhe Wei"
```

Check:
- GitHub profile display name
- GitHub bio (often contains academic affiliation)
- Paper author affiliation (if available in venue_context)

Example matches:
- GitHub: "hongbinpei" → Paper: "Hongbin Pei" ✓
- GitHub: "BingzheWei" → Paper: "Bingzhe Wei" ✓
- GitHub: "ml-lab" → Paper authors from "ML Lab @ University" ✓ (affiliation match)

## Method Name Extraction

From paper title, extract method name:

| Title pattern | Method name |
|---------------|-------------|
| "Geom-GCN: ..." | `Geom-GCN` |
| "BERT: Pre-training..." | `BERT` |
| "Attention Is All You Need" | (none, search by title) |
| "Deep Residual Learning..." | `ResNet` (if mentioned in abstract) |

Repo name matching:
- `geom-gcn` → ✓
- `GeomGCN` → ✓
- `pytorch-geom-gcn` → ✓ (framework prefix allowed)
- `geom-gcn-tutorial` → ✓ (suffix allowed)

## Common Pitfalls

| Pitfall | How to avoid |
|---------|--------------|
| **Name collision** | Verify domain matches (e.g., spatial transcriptomics paper shouldn't match image processing repo) |
| **Fork without attribution** | Check fork network, verify original repo |
| **Tutorial/educational repo** | Check README intent — might be teaching material, not implementation |
| **Abandoned repo** | Check last commit date — abandoned repos are lower confidence |
| **Multiple repos** | Same authors might have multiple repos; check which one matches paper methodology |

## Confidence Decision Flow

```
Found candidate URL
        │
        ▼
    ┌─────────────┐
    │ PDF cites   │──Yes──► HIGH + official
    │ this URL?   │
    └─────────────┘
        │No
        ▼
    ┌─────────────┐
    │ README cites│──Yes──► HIGH + official
    │ DOI/URL?    │
    └─────────────┘
        │No
        ▼
    ┌─────────────┐
    │ Author match│──Yes──► MEDIUM + official
    │ (GitHub=Paper)│
    └─────────────┘
        │No
        ▼
    ┌─────────────┐
    │ Method name │──Yes──► MEDIUM + community
    │ in repo?    │
    └─────────────┘
        │No
        ▼
    ┌─────────────┐
    │ Only title  │──Yes──► LOW + community
    │ similarity? │
    └─────────────┘
        │No
        ▼
      NONE (unrelated)
```