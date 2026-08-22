import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Validation;

extern dec requiredWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);

/** `operator` rather than `op`: `op` is a TypeSpec keyword and breaks the parser. */
extern dec computed(target: ModelProperty, operator: valueof Op, ...refs: ModelProperty[]);
