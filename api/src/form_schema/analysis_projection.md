# Form analysis projection

`form-analysis-export` derives portfolio-analysis tables from the same resolved packages that
Simpler executes. It does not compare labels or infer semantic equivalence. Only explicit semantic
identifiers participate in question reuse metrics.

```bash
cd api
uv run form-analysis-export
uv run form-analysis-export export --out ../documentation/form-analysis
uv run form-analysis-export export --form RRBudget --form RRBudget10 --out /tmp/budgets
```

The export contains form pairs, unique questions, form/question associations, all source-bound
fields, and exceptions. The association and field tables retain XML paths and exact XSD references
when packages carry them. Missing `type_source` or XML types remain blank evidence gaps; the
exporter never reconstructs them from normalized JSON types.

Forms may publish the versioned `simpler-form-field-metadata/v1` envelope at the root of their
resolved JSON Schema. When present, that contract is authoritative for applicant-question,
calculated-output, attachment, technical, and static-content classification. Its identity,
accounting, schema pointers, and question-count flags are validated before projection.

Calculated outputs, technical fields, and unresolved fields remain outside applicant-question
denominators. If a package gives one of those fields a semantic mapping, the exporter records the
contradiction, excludes it from question metrics, and marks the projection as needing
reconciliation. Accepted metrics use only mappings whose status is exactly `accepted`.
