import type { Model, ModelProperty, Program, Scalar } from "@typespec/compiler";
import {
  Block, childBlock, modelPrePopulate, propComputed, propOmit, propTotals, readBlock,
} from "../model.js";

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

/** The question a totalling rule sums. Only money is totalled. */
const MONEY_QUESTION = "generics/monetary-amount";

/**
 * One calculation. `emit` is what SGG reads; `resolve` is the same reference with the
 * array marker and the `@THIS.` shorthand removed, so that one calculation can be
 * recognized as depending on another.
 */
interface Reference {
  emit: string;
  resolve: string;
}

interface Calculation {
  /** Where the rule lands in the emitted tree, as snake-cased key parts. */
  at: string[];
  rule: string;
  refs: Reference[];
}

type Json = Record<string, unknown>;

/**
 * The complete SGG rule schema in one pass: calculations, inferred attachment validation,
 * inferred submit stamps, and declared external lookups. One producer, so the adapter
 * passes it through rather than merging into it.
 *
 * Almost none of it is written down. The attachment rule follows from a property composing
 * the attachment question; the two submit stamps from the signature and submitted-date
 * questions; a whole budget column from one `@Validation.totals`; and evaluation order
 * from how deep a calculation's dependencies go. What remains declared is only what is
 * genuinely a choice: which external source pre-populates a field.
 */
export function emitSggRules(program: Program, block: Block): Json {
  if (block.model.kind !== "Model") return {};

  const out: Json = {};
  const calculations: Calculation[] = [];
  const modelPath = new Map<Model, string[]>([[block.model, []]]);
  const context: Context = {
    prePopulate: modelPrePopulate(program, block.model),
    calculations,
    modelPath,
  };

  walk(program, block.model, [], "", out, context, true);

  // Evaluation order is a property of the dependency graph, not of the author's memory.
  const depths = new Map<string, number>();
  const byPath = new Map(calculations.map((c) => [c.at.join("."), c]));
  for (const calculation of calculations) {
    const rule: Json = {
      rule: calculation.rule,
      fields: calculation.refs.map((r) => r.emit),
    };
    const order = depth(calculation.at.join("."), byPath, depths, new Set());
    if (order >= 2) rule.order = order;
    place(out, calculation.at, { gg_pre_population: rule });
  }
  return out;
}

/** How many rounds of evaluation this calculation has to wait for. */
function depth(
  path: string,
  byPath: Map<string, Calculation>,
  memo: Map<string, number>,
  visiting: Set<string>,
): number {
  const cached = memo.get(path);
  if (cached !== undefined) return cached;
  const calculation = byPath.get(path);
  if (!calculation) return 0;
  // A cycle has no well-defined order. Report it as depth 1 rather than looping; the
  // linter is where a cycle should be caught and named.
  if (visiting.has(path)) return 1;
  visiting.add(path);
  const deepest = calculation.refs.reduce(
    (worst, ref) => Math.max(worst, depth(ref.resolve, byPath, memo, visiting)),
    0,
  );
  visiting.delete(path);
  const result = deepest + 1;
  memo.set(path, result);
  return result;
}

/** The subtree at `at`, or undefined if nothing was written there. */
function dig(root: Json, at: string[]): Json | undefined {
  let node: Json | undefined = root;
  for (const part of at) node = node?.[part] as Json | undefined;
  return node;
}

function place(root: Json, at: string[], value: Json): void {
  let node = root;
  for (const part of at.slice(0, -1)) {
    node = (node[part] as Json) ?? ((node[part] = {}) as Json);
  }
  Object.assign((node[at.at(-1)!] as Json) ?? (node[at.at(-1)!] = {}), value);
}

/** What the walk needs from the form as a whole. */
interface Context {
  /** Canonical data path -> SGG rule name, from `@Sgg.prePopulate` on the form. */
  prePopulate: Record<string, string>;
  calculations: Calculation[];
  modelPath: Map<Model, string[]>;
}

function walk(
  program: Program,
  model: Model,
  at: string[],
  dataPath: string,
  into: Json,
  context: Context,
  atRoot: boolean,
): void {
  const { calculations, modelPath } = context;
  for (const prop of [...model.properties.values()].filter((p) => !propOmit(program, p))) {
    const key = prop.name;
    const here = [...at, key];
    const path = dataPath ? `${dataPath}.${prop.name}` : prop.name;
    const child = childBlock(program, prop);

    const totals = propTotals(program, prop);
    if (totals && child && !child.scalar && child.model.kind === "Model") {
      collectTotals(program, prop, child, here, at, modelPath, calculations);
      continue;
    }

    const computed = propComputed(program, prop);
    if (computed) {
      calculations.push({
        at: here,
        rule: OP_RULE[computed.operator] ?? "sum_monetary",
        refs: computed.refs.map((name) => ({
          // A sibling reference is spelled `@THIS.` everywhere but the form's own root.
          emit: atRoot ? name : `@THIS.${name}`,
          resolve: [...at, name].join("."),
        })),
      });
      continue;
    }

    if (child) {
      const stamp = STAMP_BY_QUESTION[child.id];
      if (stamp) {
        place(into, here, { gg_post_population: { rule: stamp } });
        continue;
      }
      if (child.id === ATTACHMENT_QUESTION) {
        place(into, here, { gg_validation: { rule: "attachment" } });
        continue;
      }
      if (child.scalar) {
        const rule = context.prePopulate[path];
        if (rule) place(into, here, { gg_pre_population: { rule } });
        continue;
      }
      modelPath.set(child.model as Model, here);
      walk(program, child.model as Model, here, path, into, context, false);
      continue;
    }

    // A repeatable list of objects: SGG marks the node so its rules apply per entry.
    if (prop.type.kind === "Model" && prop.type.indexer) {
      const item = prop.type.indexer.value;
      const itemBlock =
        item.kind === "Model" || item.kind === "Scalar" ? readBlock(program, item) : undefined;
      if (itemBlock?.id === ATTACHMENT_QUESTION) {
        place(into, here, { gg_validation: { rule: "attachment" } });
        continue;
      }
      if (item.kind === "Model") {
        // Walk into a throwaway tree first: the node is only marked as an array if the
        // entries turn out to carry rules.
        const nested: Json = {};
        const nestedCalculations: Calculation[] = [];
        modelPath.set(item, here);
        walk(program, item, here, path, nested, { ...context, calculations: nestedCalculations }, false);
        const entryRules = (dig(nested, here) ?? {}) as Json;
        if (Object.keys(entryRules).length || nestedCalculations.length) {
          place(into, here, { gg_type: "array", ...entryRules });
          calculations.push(...nestedCalculations);
        }
      }
      continue;
    }

    if (prop.type.kind === "Model") {
      modelPath.set(prop.type, here);
      walk(program, prop.type, here, path, into, context, false);
      continue;
    }

    const rule = context.prePopulate[path];
    if (rule) place(into, here, { gg_pre_population: { rule } });
  }
}

/**
 * Expand one `@Validation.totals` into a calculation per money field of the block.
 *
 * Two shapes of source, and the difference is visible in the type: a repeatable list, so
 * the block is found inside each entry and every entry contributes; or a peer property
 * holding the same block, so the two named columns contribute.
 */
function collectTotals(
  program: Program,
  target: ModelProperty,
  block: Block,
  at: string[],
  parent: string[],
  modelPath: Map<Model, string[]>,
  calculations: Calculation[],
): void {
  const sources = propTotals(program, target)!;
  const model = block.model as Model;

  for (const field of moneyFields(program, model)) {
    const refs: Reference[] = [];
    for (const source of sources) {
      const type = source.type;
      if (type.kind === "Model" && type.indexer) {
        const item = type.indexer.value;
        if (item.kind !== "Model") continue;
        const inner = sameBlock(program, item, block);
        if (!inner) continue;
        const base = [...(modelPath.get(source.model as Model) ?? []), source.name];
        refs.push({
          emit: `${base.join(".")}[*].${inner.name}.${field}`,
          resolve: [...base, inner.name, field].join("."),
        });
        continue;
      }
      // A peer holding the same block: its path is this target's parent plus its name.
      const base = [...(modelPath.get(source.model as Model) ?? parent), source.name];
      refs.push({
        emit: [...base, field].join("."),
        resolve: [...base, field].join("."),
      });
    }
    if (!refs.length) continue;
    calculations.push({ at: [...at, field], rule: "sum_monetary", refs });
  }
}

/** The money-valued fields of a block, in declaration order. */
function moneyFields(program: Program, model: Model): string[] {
  const out: string[] = [];
  for (const prop of model.properties.values()) {
    const child = childBlock(program, prop);
    if (child?.id === MONEY_QUESTION) out.push(prop.name);
  }
  return out;
}

/** The property of `item` that holds the same block as `block`. */
function sameBlock(program: Program, item: Model, block: Block): ModelProperty | undefined {
  const matches = [...item.properties.values()].filter((prop) => {
    const type = prop.type as Model | Scalar;
    return (type.kind === "Model" || type.kind === "Scalar") && type === block.model;
  });
  return matches.length === 1 ? matches[0] : undefined;
}
