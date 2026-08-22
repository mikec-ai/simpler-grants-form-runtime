import type { Program } from "@typespec/compiler";
import { Block, orderedProps, propRequiredWhen } from "../model.js";

/**
 * The only part of a block's JSON Schema that `@typespec/json-schema` cannot
 * produce: conditional requiredness derived from `@Validation.requiredWhen`.
 * Everything else — types, constraints, enums, arrays, `required`, `$ref`
 * composition, `extends` as `allOf` — comes from the stock emitter.
 *
 * The build merges this over the stock output.
 */
export function emitSchemaOverlay(
  program: Program,
  block: Block,
): Record<string, unknown> | undefined {
  if (block.scalar) return undefined;

  const conditionals: Record<string, unknown>[] = [];
  for (const prop of orderedProps(program, block)) {
    for (const c of propRequiredWhen(program, prop)) {
      conditionals.push({
        if: {
          properties: {
            [c.sourceName]: c.sourceIsArray
              ? { contains: { const: c.value } }
              : { const: c.value },
          },
          // The guard idiom from forms/README.md: only run when the source is set.
          required: [c.sourceName],
        },
        then: { required: [prop.name] },
      });
    }
  }
  if (!conditionals.length) return undefined;

  // Merge conditionals sharing an identical `if`, as the golden artifacts do.
  const merged: Record<string, unknown>[] = [];
  for (const c of conditionals) {
    const twin = merged.find((m) => JSON.stringify(m.if) === JSON.stringify(c.if));
    if (twin) {
      (twin.then as { required: string[] }).required.push(
        ...(c.then as { required: string[] }).required,
      );
    } else merged.push(c);
  }
  return { allOf: merged };
}
