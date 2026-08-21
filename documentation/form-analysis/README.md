# Implementation-derived form analysis

These tables are generated from the native form packages in this repository. Run:

```bash
cd api
uv run form-analysis-export export --out ../documentation/form-analysis
```

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
mappings are agent-proposed, so accepted coverage remains zero. Blank XML type cells mean the
implementation package has not preserved that evidence yet; the exporter does not infer XML types
from JSON types.

PHS Fellowship Supplemental exercises the versioned `simpler-form-field-metadata/v1` handoff. Its
47 applicant questions, 2 calculated outputs, 17 attachments, and 99 technical/structural records
project without reclassification, and its form-question rows retain complete XML type and XSD
evidence.
