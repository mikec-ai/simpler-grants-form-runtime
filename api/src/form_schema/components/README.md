# Application components

Application components capture exact question-level structure and behavior that
is reused across otherwise different forms. Unlike form templates, a component
may contribute only part of a form and may span JSON Schema, UI, rule, and XML
artifacts.

Components are native resolved runtime definitions, not an independent semantic
authority. Their builders expose genuine form-level presentation or wire deltas
explicitly and share only behavior demonstrated by supported forms.

This boundary is compatible with a future canonical question source such as
CommonGrants: a build-time compiler can resolve canonical questions into these
component contributions or directly into a resolved form package. Simpler does
not need to import an external authoring system at runtime.

The first component covers applicant organization identity. SF-424 and SF-424
Short share organization-name and SAM UEI schemas, UEI prepopulation, and XML
targets while preserving their exact descriptions and editable/read-only UI
differences.
