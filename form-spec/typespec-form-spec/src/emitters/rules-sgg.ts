import type { Program } from "@typespec/compiler";
import { Block, childBlock, orderedProps, propComputed, propPrePopulate, readBlock } from "../model.js";

const snake = (s: string) => s.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
const OP_RULE: Record<string, string> = {
  Sum: "sum_monetary",
  Subtract: "subtract_monetary",
  PercentOf: "multiply_by_percentage",
};

/** Question ids whose presence implies a submit-time stamp (Tier 2, inferred). */
const STAMP_BY_QUESTION: Record<string, string> = {
  "generics/signature": "signature",
  "generics/submitted-date": "current_date",
};

/**
 * The attachment question, wherever it appears, implies SGG's attachment validation rule.
 * Inferred from the question's identity rather than from the shape of its type: an
 * attachment is a string carrying a file id, and so is a great many other things.
 */
const ATTACHMENT_QUESTION = "generics/attachment";

/**
 * The complete SGG rule schema, in one pass: calculations, inferred attachment
 * validation, inferred submit stamps, and declared external lookups. One producer,
 * so the adapter passes it through rather than merging into it.
 */
function calculation(calc: { operator: string; refs: string[] }): Record<string, unknown> {
  return {
    gg_pre_population: {
      rule: OP_RULE[calc.operator] ?? "sum_monetary",
      fields: calc.refs.map(snake),
    },
  };
}

export function emitSggRules(program: Program, block: Block): Record<string, unknown> {
  const out: Record<string, unknown> = {};

  const walk = (b: Block, container: Record<string, unknown>): void => {
    for (const prop of orderedProps(program, b)) {
      const key = snake(prop.name);
      const child = childBlock(program, prop);

      if (child) {
        // Tier 2: a stamp question implies a post-population rule.
        const stamp = STAMP_BY_QUESTION[child.id];
        if (stamp) {
          container[key] = { gg_post_population: { rule: stamp } };
          continue;
        }
        if (child.id === ATTACHMENT_QUESTION) {
          container[key] = { gg_validation: { rule: "attachment" } };
          continue;
        }
        if (child.scalar) {
          const calc = propComputed(program, prop);
          if (calc) {
            container[key] = calculation(calc);
            continue;
          }
          const rule = propPrePopulate(program, prop);
          if (rule) container[key] = { gg_pre_population: { rule } };
          continue;
        }
        const nested: Record<string, unknown> = {};
        walk(child, nested);
        if (Object.keys(nested).length) container[key] = nested;
        continue;
      }

      // Tier 1: an array of attachments carries the same rule as one attachment.
      if (prop.type.kind === "Model" && prop.type.indexer) {
        const item = prop.type.indexer.value;
        const itemBlock =
          item.kind === "Model" || item.kind === "Scalar" ? readBlock(program, item) : undefined;
        if (itemBlock?.id === ATTACHMENT_QUESTION) {
          container[key] = { gg_validation: { rule: "attachment" } };
          continue;
        }
      }

      // Calculations.
      const calc = propComputed(program, prop);
      if (calc) {
        container[key] = calculation(calc);
        continue;
      }

      // Tier 3: declared external lookups.
      const rule = propPrePopulate(program, prop);
      if (rule) container[key] = { gg_pre_population: { rule } };
    }
  };

  walk(block, out);
  return out;
}
