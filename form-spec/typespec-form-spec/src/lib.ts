import { createTypeSpecLibrary, paramMessage } from "@typespec/compiler";

export const $lib = createTypeSpecLibrary({
  name: "@simpler-grants/form-spec",
  diagnostics: {
    "form-scoped-question-id": {
      severity: "error",
      messages: {
        default: paramMessage`Question id "${"id"}" names a form. Questions are named for meaning; put form deltas in overrides.`,
      },
    },
    "condition-value-not-in-enum": {
      severity: "error",
      messages: {
        default: paramMessage`Value "${"value"}" is not a member of enum ${"enumName"}.`,
      },
    },
    "sgg-outside-forms": {
      severity: "error",
      messages: {
        default: paramMessage`@Sgg.* may only appear in specs/forms/; found on ${"target"}.`,
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
    multiField: {},
    prePopulate: {},
  },
} as const);

export const { reportDiagnostic, createDiagnostic, stateKeys } = $lib;
