import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Question;

/**
 * A bank question. Object-valued questions are Models; single-value questions
 * (a phone number, an email address, an organization name) are Scalars.
 */
extern dec meta(target: Model | Scalar, meta: valueof QuestionMeta);
