# Portable form specifications

This directory is a dependency-neutral canary for reusable grants-form declarations.

The portable contract is referenced JSON Schema Draft 2020-12 plus JSON Forms UI schemas,
mapping sidecars, exact source evidence, and review boundaries. Simpler consumes the bundle
through a generic adapter in `api/src/form_schema/portable_form_bundle.py`; the specifications
do not import or execute Simpler code.

The first canary intentionally models only the applicant organization legal-name question in
two forms. It proves shared semantic identity and different source-wire bindings without
claiming either form is complete or that its agent-proposed mapping has been accepted.

TypeSpec and CommonGrants are optional compatibility inputs. Neither is required to author,
validate, analyze, or load this bundle.
