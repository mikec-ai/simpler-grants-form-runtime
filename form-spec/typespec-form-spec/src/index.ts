export { $onEmit } from "./emitter.js";
import * as d from "./decorators.js";

export { $lib } from "./lib.js";
export * from "./decorators.js";

export const $decorators = {
  "SimplerForms.Question": { meta: d.$questionMeta },
  "SimplerForms.Form": { meta: d.$formMeta },
  "SimplerForms.Catalog": { tag: d.$tag, entity: d.$entity },
  "SimplerForms.UI": {
    sections: d.$sections,
    section: d.$section,
    overrides: d.$overrides,
    label: d.$label,
    helpText: d.$helpText,
    widget: d.$widget,
    order: d.$order,
    omit: d.$omit,
    readOnly: d.$readOnly,
    visibleWhen: d.$visibleWhen,
    readOnlyWhen: d.$readOnlyWhen,
  },
  "SimplerForms.Validation": { requiredWhen: d.$requiredWhen, computed: d.$computed },
  "SimplerForms.Sgg": { prePopulate: d.$prePopulate },
};
