# Portable form analysis artifacts

Question-level analysis is derived from the canonical declarations in `form-specs/`.
Generated JSON, CSV, and XLSX files are intentionally not checked into this runtime
repository.

The `Portable Form Build Artifacts` workflow publishes two downloadable artifacts for
each relevant pull request and each update to `main` or the private `mirror-base` branch:

- `portable-form-oracles-<commit>` contains resolved runtime packages, native
  implementation snapshots for forms with an existing implementation, a parity report,
  and a hash manifest.
- `portable-form-analysis-<commit>` contains the complete JSON projection, CSV decision
  tables, the Excel workbook, and checksums.

Generate the same outputs locally:

```bash
uv run --project api python scripts/export_portable_form_oracles.py
uv run --project api python scripts/export_portable_form_analysis.py \
  --output-dir build/portable-form-artifacts/analysis
uv run --project api python scripts/build_portable_form_analysis_workbook.py \
  --analysis-dir build/portable-form-artifacts/analysis \
  --output build/portable-form-artifacts/analysis/form-analysis.xlsx
```

Canonical form declarations, source provenance, review boundaries, and bounded evidence
remain versioned. Generated snapshots and analytical projections do not serve as runtime
inputs.
