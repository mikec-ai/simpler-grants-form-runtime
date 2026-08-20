# Form templates

Form templates capture structure and behavior that is already shared by multiple
supported forms. A template builder accepts explicit, source-specific parameters
and returns a fully resolved `FormDefinition` containing the JSON Schema, UI
schema, rule schema, XML transform rules, and `Form` metadata.

Template composition happens when the versioned form module is imported. The
registry still receives an ordinary `Form`, so API and frontend consumers do not
need template-specific runtime behavior.

"Template" is deliberately distinct from the official form-family groupings in
the Grants.gov forms repository. Cross-form domain concepts such as people,
organizations, budgets, and sub-awards should be modeled separately as reusable
application components. An attachment is a response mechanism for content, not
itself a reusable question type.

## Design constraints

- Keep every form's identifiers, labels, source URLs, versions, XML namespaces,
  and other genuine differences explicit in its versioned module.
- Share only structure and behavior that the supported forms demonstrably have
  in common.
- Return new artifact objects for every build so one form cannot mutate another.
- Declare shared source dependencies in each version's
  `version_dependencies.txt`. The version lock hashes those dependencies so a
  shared-template change invalidates every affected form checksum.
- Preserve the existing version directory and locking model. Published versions
  remain independently testable, and adding a new template variant does not mutate
  the artifact objects allocated for an existing version.
- Add template-level tests for shared behavior and retain form-level tests for each
  variant's exact contract.

The narrative attachment template is the first implementation. Project, Other,
and Budget Narrative attachments reuse one attachment schema, UI shape,
validation rule, and XML structure while declaring their exact metadata and
wire identifiers separately.
