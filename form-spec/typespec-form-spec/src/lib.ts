import { createTypeSpecLibrary, paramMessage } from "@typespec/compiler";

/**
 * Named diagnostics for everything that makes an artifact wrong, and state keys for
 * everything the decorators record.
 *
 * The split between these and the linter rules in `linter.ts` is forced rather than
 * chosen: a TypeSpec linter rule may only be a warning. So a check whose failure means the
 * emitted artifact is broken is reported from `$onValidate` as an error, and the linter
 * carries the checks that describe a specification worth tidying.
 */
export const $lib = createTypeSpecLibrary({
  name: "@simpler-grants/form-spec",
  diagnostics: {
    "form-scoped-question-id": {
      severity: "error",
      messages: {
        default: paramMessage`Question id "${"id"}" names a form. Questions are named for what they mean; put form deltas in @UI.overrides.`,
      },
    },
    "duplicate-block-id": {
      severity: "error",
      messages: {
        default: paramMessage`Block id "${"id"}" is claimed by both ${"first"} and ${"second"}. Two blocks would collide on one output path; a form-local extension should use \`extends\`, which carries no identity.`,
      },
    },
    "condition-value-not-in-enum": {
      severity: "error",
      messages: {
        default: paramMessage`"${"value"}" is not a member of ${"enumName"}, so this condition can never hold. Members: ${"members"}.`,
      },
    },
    "calculation-cycle": {
      severity: "error",
      messages: {
        default: paramMessage`Calculation cycle: ${"cycle"}. A calculated value cannot depend on itself.`,
      },
    },
    "required-but-unreachable": {
      severity: "error",
      messages: {
        default: paramMessage`${"name"} is always required but only sometimes visible, so an applicant can be blocked by a field they cannot see. Make it optional and use @Validation.requiredWhen, or drop the visibility condition.`,
      },
    },
    "override-path-unresolved": {
      severity: "error",
      messages: {
        default: paramMessage`@UI.overrides path "${"path"}" does not resolve: ${"reason"}.`,
      },
    },
    "section-orphan": {
      severity: "error",
      messages: {
        default: paramMessage`${"name"} is in no section, so it renders nowhere. Give it a @UI.section, or @UI.omit it if that is deliberate.`,
      },
    },
    "sgg-outside-forms": {
      severity: "error",
      messages: {
        default: paramMessage`@Sgg.${"decorator"} is a target vocabulary and may only appear on a form. ${"name"} is in the question bank.`,
      },
    },
  },
  state: {
    questionMeta: {},
    formMeta: {},
    tags: {},
    entity: {},
    label: {},
    helpText: {},
    widget: {},
    sections: {},
    section: {},
    order: {},
    overrides: {},
    readOnly: {},
    omit: {},
    visibleWhen: {},
    readOnlyWhen: {},
    requiredWhen: {},
    computed: {},
    totals: {},
    prePopulate: {},
    multiField: {},
  },
} as const);

export const { reportDiagnostic, createDiagnostic, stateKeys } = $lib;
