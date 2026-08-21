# R&R SF-424 source review

This read-only review covered all 13 instruction pages, both readonly-form pages,
the XFA fallback page, extracted text, reconciliation evidence, and the embedded XFA
template. It records implementation gates; it does not approve semantic mappings or
make this draft eligible for published coverage.

## Reviewed sources

- Instructions PDF SHA-256:
  `666647fdeb7d9d69f2d36dedc74f09ff6a9540776f87c5a5c5b0593219736bd1`
- Readonly-form PDF SHA-256:
  `592a1faf1cfdac3e350a22c6fbae3b8c6f229b6c7de29ec18273b60c9235dd6b`
- Canonical XFA sample SHA-256:
  `06dd92da28b4afb8190fd0edaeb7a0dac3ae2d601adcc1ab9a5e0fc93c09f523`

## Verified PR14 baseline gap

The PR14 baseline preserved 107 leaves and 145 DAT behavior records, but executed only
the three attachment-type checks. Later behavior slices are tracked against this queue.
The executed slice is reconciled one-to-one to exact DAT behavior keys and pinned
PDF/XFA findings in `behavior-evidence.json`; every record remains coverage-ineligible.
The XFA contains 97 validations, 137 tooltips, 186
events, 196 scripts, and four calculation nodes. Those four cover UEI/population,
Assistance Listing number/title, and an internal email-match helper. The XFA does not
calculate the four funding totals.

`ApplicantInfo.OrganizationInfo.EIN` is XSD-derived but has no canonical XFA binding.
The user-facing EIN is the top-level `EmployerID`; the nested field must be hidden or
classified as internal rather than rendered as a second EIN.

## Executed behavior slices

- Conditional requiredness and presentation for Federal ID, previous tracking ID,
  Applicant Other, other-agency explanation, state-review date, and small-business
  attributes.
- Required affirmative certification, three email formats, UEI length, opportunity
  population, and submission-managed AOR signature/date.
- US State and ZIP versus non-US Province across all four address roles, including the
  nine-character US ZIP minimum.
- Missing applicant and application-contact countries default to USA without replacing
  a user's existing non-US selection.
- Applicant organization and address values initially copy into the PD/PI and AOR
  profiles. Any later user overwrite, including an intentionally blank value, is
  preserved on subsequent lifecycle population passes.
- Revision details render as the canonical five checkboxes while preserving the encoded
  XML value, accept only the source-defined single/pair combinations, require an Other
  explanation for E, and clear dependent values when the application type changes.
- Applicant congressional district uses the source-prescribed `CA-005` or `00-000`
  structure.
- Project end date cannot precede project start date.
- All four funding amounts preserve the source range and two-decimal precision as
  independently applicant-entered values; no funding calculation was introduced.

## Priority behavior queue

1. Presentation and instructions:
   - Restore numbered order 1-21, human labels, help text, certification language,
     attachment-role guidance, OMB metadata, expiration, and burden-statement access.

## Human-resolution queue

- Metadata expiration `11/30/2025` conflicts with PDF expiration `01/31/2029`.
- Instructions cite Executive Order `12732`; the rendered form cites `12372`.
- Applicant Province prose conflicts with DAT/XFA activation behavior.
- Applicant ZIP prose incorrectly references the project performance site.
- PD/PI Street 2 prose says required although XFA and visual treatment make it optional.
- Revision prose broadly permits multiple selections, while DAT/XFA restrict valid pairs
  to AC, AD, BC, or BD and make E exclusive.

Shared primitives remain appropriate, but application contact, PD/PI, and AOR are
distinct semantic roles. Structurally valid XML is not evidence that these runtime
behaviors have been satisfied.
