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

## Verified implementation gap

The draft preserves 107 leaves and 145 DAT behavior records, but executes only the
three attachment-type checks. The XFA contains 97 validations, 137 tooltips, 186
events, 196 scripts, and four calculation nodes. Those four cover UEI/population,
Assistance Listing number/title, and an internal email-match helper. The XFA does not
calculate the four funding totals.

`ApplicantInfo.OrganizationInfo.EIN` is XSD-derived but has no canonical XFA binding.
The user-facing EIN is the top-level `EmployerID`; the nested field must be hidden or
classified as internal rather than rendered as a second EIN.

## Priority behavior queue

1. Conditional requiredness and presentation:
   - Federal ID for Renewal, Continuation, and Revision.
   - Previous tracking ID for Changed/Corrected submissions.
   - US State and ZIP versus non-US Province for all four address roles.
   - Applicant Other, revision details/Other, other-agency explanation, and
     state-review date.
   - Revision checkbox combinations and stale-value clearing.
   - Small-business attributes only for applicant type R.
   - Required affirmative certification; `N: No` must not satisfy it.
2. Lifecycle population:
   - Default applicant and application-contact country to USA.
   - Populate Assistance Listing number/title and federal agency from opportunity data.
   - Enforce and protect the 12-character UEI.
   - Copy applicant organization/address into initially empty PD/PI and AOR fields,
     while allowing overwrite.
   - Make AOR signature/date submission-managed rather than ordinary editable fields.
3. Validation:
   - Contact, PD/PI, and AOR email validation; contact email remains optional.
   - Project start date must not follow end date.
   - Congressional district format (`CA-005` or `00-000`).
   - Funding range 0-9,999,999,999,999.99 with at most two decimal places.
   - Do not add a 15c funding calculation without an explicit reviewed decision.
4. Presentation and instructions:
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
