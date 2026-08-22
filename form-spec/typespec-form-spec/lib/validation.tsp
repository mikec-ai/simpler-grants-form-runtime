// The JS that implements the `extern dec` declarations below. Imported here rather than
// only from `main.tsp` so that this file type-checks on its own -- an editor opens one
// file, not an entry point, and an unimplemented `extern dec` is an error.
import "../dist/src/index.js";
import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Validation;

extern dec requiredWhen(target: ModelProperty, source: ModelProperty, equals: valueof unknown);

/** `operator` rather than `op`: `op` is a TypeSpec keyword and breaks the parser. */
extern dec computed(target: ModelProperty, operator: valueof Op, ...refs: ModelProperty[]);

/**
 * This block totals the same block found in each of `sources`, field by field.
 *
 * A source is either a repeatable list -- in which case the corresponding block is found
 * inside each entry -- or a peer property holding the same block. Either way one
 * declaration stands for a sum per field, which is what makes a twelve-row budget column
 * one statement rather than twelve.
 */
extern dec totals(target: ModelProperty, ...sources: ModelProperty[]);
