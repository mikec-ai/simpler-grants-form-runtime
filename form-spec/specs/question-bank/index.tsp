import "@typespec/json-schema";
import "@simpler-grants/form-spec";

/**
 * No base URI is declared. A block's identity is its `@Question.meta.id`; where the
 * artifacts are hosted is a per-consumer decision, so the base is supplied at build
 * time (`scripts/merge.mjs --base`) rather than baked into the specs.
 */
@JsonSchema.jsonSchema
namespace QuestionBank;
