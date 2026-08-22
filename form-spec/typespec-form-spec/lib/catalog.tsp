import "./types.tsp";

using TypeSpec.Reflection;

namespace SimplerForms.Catalog;

extern dec tag(target: Model, ...tags: valueof TagName[]);
extern dec entity(target: Model, entity: valueof EntityName);
