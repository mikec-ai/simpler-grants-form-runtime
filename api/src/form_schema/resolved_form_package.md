# Resolved form packages

`common-grants-resolved-form-package/v1` is a build-time boundary between a
compositional form authoring system and Simpler's native form runtime.

The package contains already-resolved JSON Schema, Simpler UI schema, rule
schema, CommonGrants mappings, and optional XML transformation artifacts. The
loader does not import TypeSpec, call a remote service, or understand a specific
authoring repository. It verifies every artifact hash and returns an ordinary
native `Form`.

## Ownership boundary

- CommonGrants owns canonical questions, role-qualified mappings, and composed
  TypeSpec form definitions.
- A deterministic compiler resolves question references, applies bounded form
  overrides, and projects the UI contract before packaging.
- Simpler owns rendering, validation, calculations, conditional interaction,
  application persistence, and receiving-system XML generation.

Resolved artifacts may repeat shared schema content. They are immutable runtime
snapshots, not independently maintained form source code. The manifest retains a
declared CommonGrants repository revision, verified local source snapshots,
question-to-form bindings, compiler status, and review boundary. Offline loading
proves package integrity; it does not independently authenticate that a Git host
associates those bytes with the declared revision. A production-eligible
publisher must provide that trust through a pinned release, trusted checkout, or
signature before packaging.

The v1 loader currently recognizes only `snapshot_only` source attestation. A
manifest must say whether its source graph is complete or partial and must carry
the digest of that canonical graph. Snapshot-only, partial, manually compiled,
agent-proposed, or model-unvalidated packages can never be marked eligible for
published coverage.

## Safety properties

- Unknown or missing manifest keys fail closed.
- Artifact paths cannot be absolute, traverse above the package, or resolve
  through a symlink outside it.
- Every artifact is verified against a lowercase SHA-256 digest before parsing.
- Every bound question must occur in the pinned source set.
- Every binding pointer and direct form-side mapping path must resolve against
  the packaged JSON Schema, and the bound node must declare the same question ID.
- CommonGrants mappings are copied into the native JSON Schema as annotations;
  a conflicting embedded mapping fails rather than being overwritten.
- Verified values are retained as private canonical JSON. Public accessors and
  every call to `to_form()` return independently allocated values.
- The native JSON Schema retains package digest, source, compiler, question
  binding, and review metadata under `x-simpler-form-package`.
- `dependency_paths` exposes the manifest, pinned source snapshots, and resolved
  artifacts that a versioned form must include in its immutable-version lock.

The first compatibility fixture projects the organization-name slice of the
CommonGrants Key Contact source. Its raw question semantics, role, question-local
mappings, and form label override are exact source snapshots. Rebasing those
mappings into a form and projecting the surrounding Simpler section are marked
agent-proposed, the CommonGrants target model has not yet been conformance
validated, and the compiler is explicitly a manual canary. The loader therefore
rejects any attempt to mark this fixture as published-coverage eligible. This is
a contract test, not a claim that the partial fixture or current CommonGrants
form is production-equivalent to Grants.gov or Nava's form.
