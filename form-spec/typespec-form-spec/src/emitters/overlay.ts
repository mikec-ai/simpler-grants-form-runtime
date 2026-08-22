import type { Program } from "@typespec/compiler";
import { Block, orderedProps, propRequiredWhen } from "../model.js";

/**
 * The parts of a block's JSON Schema that `@typespec/json-schema` cannot produce.
 *
 * Two of them. Conditional requiredness, from `@Validation.requiredWhen`. And the
 * presentation a *form* puts on a member of a question it composes, from `@UI.overrides` --
 * SF-424 calls the authorized representative's phone "AOR Telephone Number" where the
 * question calls it "Telephone Number", and that belongs to the form.
 *
 * Everything else -- types, constraints, enums, arrays, `required`, `$ref` composition,
 * `extends` as `allOf` -- comes from the stock emitter. The build merges this over it.
 */
export function emitSchemaOverlay(
  program: Program,
  block: Block,
): Record<string, unknown> | undefined {
  const conditionals = conditionalRequiredness(program, block);
  const patches = overriddenPresentation(block);
  if (!conditionals && !patches) return undefined;
  return { ...(conditionals ?? {}), ...(patches ?? {}) };
}

function conditionalRequiredness(
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

/**
 * A form's own label and help text for a member of a question it composes.
 *
 * The member's schema is behind a `$ref`, so the patch goes beside it: a second `allOf`
 * branch naming the member. A consumer that resolves the reference sees the question's
 * wording, then the form's on top -- which is the order that makes the form win.
 */
function overriddenPresentation(block: Block): Record<string, unknown> | undefined {
  const patches: Record<string, Record<string, unknown>> = {};
  for (const [path, override] of Object.entries(block.overrides)) {
    const presentation: Record<string, unknown> = {};
    if (typeof override.label === "string") presentation.title = override.label;
    if (typeof override.helpText === "string") presentation.description = override.helpText;
    if (!Object.keys(presentation).length) continue;

    const [head, ...rest] = path.split(".");
    if (!rest.length) {
      // A root property is declared in this block, so `@UI.label` already covers it.
      continue;
    }
    const patch = nest(rest, presentation);
    patches[head] = merge(patches[head] ?? {}, patch);
  }
  if (!Object.keys(patches).length) return undefined;
  return {
    properties: Object.fromEntries(
      Object.entries(patches).map(([name, patch]) => [name, { allOf: [patch] }]),
    ),
  };
}

/** `["phone"], {title}` becomes `{properties: {phone: {title}}}`. */
function nest(steps: string[], leaf: Record<string, unknown>): Record<string, unknown> {
  return steps.reduceRight<Record<string, unknown>>(
    (inner, step) => ({ properties: { [step]: inner } }),
    leaf,
  );
}

function merge(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...a };
  for (const [key, value] of Object.entries(b)) {
    const existing = out[key];
    out[key] =
      isRecord(existing) && isRecord(value) ? merge(existing, value) : value;
  }
  return out;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
