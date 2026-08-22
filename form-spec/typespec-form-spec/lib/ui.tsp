import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.UI;

/** Declare the ordered section set for a block. */
extern dec sections(target: Model, sections: Enum);

/** Assign a property (and everything under it) to one section. */
extern dec section(target: ModelProperty, section: valueof EnumMember);

/** Form-scoped override table, keyed by dotted path relative to the target. */
extern dec overrides(target: Model | ModelProperty, patch: valueof Record<unknown>);

extern dec label(target: Model | ModelProperty, text: valueof string);
extern dec helpText(target: ModelProperty, text: valueof string);
extern dec widget(target: ModelProperty, widget: valueof WidgetName);
extern dec order(target: Model, ...props: ModelProperty[]);
extern dec omit(target: ModelProperty);
extern dec readOnly(target: ModelProperty);

extern dec visibleWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);
extern dec readOnlyWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);
