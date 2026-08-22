// The JS that implements the `extern dec` declarations below. Imported here rather than
// only from `main.tsp` so that this file type-checks on its own -- an editor opens one
// file, not an entry point, and an unimplemented `extern dec` is an error.
import "../dist/src/index.js";
import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Question;

/**
 * A bank question. Object-valued questions are Models; single-value questions
 * (a phone number, an email address, an organization name) are Scalars.
 */
extern dec meta(target: Model | Scalar, meta: valueof QuestionMeta);
