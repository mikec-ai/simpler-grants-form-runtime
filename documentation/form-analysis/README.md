# Implementation-derived form analysis

These tables are generated from the native form packages in this repository. Run:

```bash
cd api
uv run form-analysis-export export --out ../documentation/form-analysis
```

`form-analysis.xlsx` combines the generated tables into one filterable workbook. Its `Start Here`
sheet summarizes the current scope and explains where to answer each analytical question.

The primary analysis tables are:

- `form_pairs.csv`: every implemented form pair, with Jaccard similarity, shared-question count,
  and both directional coverage measures.
- `questions.csv`: each explicit canonical question and the number of implemented forms in which
  it occurs.
- `form_questions.csv`: every form/question occurrence, including runtime and XML paths, XML type
  evidence, XSD source, role, dimensions, components, and mapping status.

`forms.csv` summarizes each form. `fields.csv` retains the complete field inventory, including
calculated outputs, technical fields, and unmapped fields. `exceptions.csv` records contradictions
that must be reconciled, such as calculated outputs carrying stale semantic question identifiers.
`projection.json` is the lossless machine-readable bundle, and `manifest.json` pins every output
by row count and SHA-256 digest.

The current tables cover the nine forms with native source packages on this branch. Similarity is
computed only from explicit canonical identifiers, never from labels. All current semantic
mappings are agent-proposed, so accepted coverage remains zero. Every applicant-question row now
retains its exact XML path, source type, cardinality, XSD URL, and XSD digest. Blank role,
dimension, component, or behavior cells mean that attribute does not apply or is not established
by the pinned evidence; the exporter does not invent values to fill them.

All nine forms exercise the versioned `simpler-form-field-metadata/v1` handoff. The source-ledger
backfill also corrects two analytical defects in the former runtime-schema fallback: SF-424 now
contributes 71 source-bound applicant questions rather than zero, and the 5-year and 10-year R&R
Subaward Budget variants now share the same 98-question denominator. Four R&R Budget personnel-role
records still lack semantic identifiers and appear explicitly in `exceptions.csv` for reconciliation.
