# R&R SF-424 v5.0 draft package

This version-local package makes the source-derived R&R SF-424 projection renderable in
the private Simpler mirror. It establishes a locked baseline before reusable native
components replace matching portions of the resolved form.

What is verified here:

- 139 pinned XSD/DAT source records produce 107 countable form fields.
- Every one of the 107 UI pointers resolves to the packaged JSON Schema.
- The XML transform retains the `RR_SF424_5_0` v5.0 root, namespaces, sequence plan,
  nested object mappings, and three attachment slots.
- The version lock covers every packaged artifact.

What is not claimed:

- The agent-proposed semantic mappings, labels, sections, and field modes have not
  received product/policy approval.
- PDF instructions and policy content are not complete.
- The form has not completed accessibility, human acceptance, deployment, or release
  review.
- It is not eligible for published coverage and is not production-ready.

The `[Draft]` runtime name and the fail-closed manifest boundary are intentional. They
allow local integration and component-parity work without presenting this package as an
upstream or Grants.gov release.
