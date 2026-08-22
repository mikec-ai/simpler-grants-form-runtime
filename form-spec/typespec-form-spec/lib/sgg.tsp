// The JS that implements the `extern dec` declarations below. Imported here rather than
// only from `main.tsp` so that this file type-checks on its own -- an editor opens one
// file, not an entry point, and an unimplemented `extern dec` is an error.
import "../dist/src/index.js";
import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Sgg;

extern dec prePopulate(target: ModelProperty, rule: valueof SggPrePop);

/**
 * Hand an entire section to one of SGG's bespoke widgets.
 *
 * SGG renders the budget sections with purpose-built components rather than from a field
 * list. The component receives the section's properties, which `@UI.section` already
 * says -- so the only thing left to declare is which component, and that is a fact about
 * SGG's renderer rather than about the form. Hence its living here: the canonical UI
 * artifact still describes the section as a group of controls, and a renderer that does
 * not have these six components uses that.
 */
extern dec multiField(target: Model, section: valueof EnumMember, widget: valueof WidgetName);
