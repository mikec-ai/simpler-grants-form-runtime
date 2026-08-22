import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Catalog;

extern dec tag(target: Model | Scalar, ...tags: valueof TagName[]);
extern dec entity(target: Model | Scalar, entity: valueof EntityName);
