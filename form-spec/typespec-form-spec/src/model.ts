import type {
  Enum, EnumMember, Model, ModelProperty, Program, Scalar, Type,
} from "@typespec/compiler";
import { getDoc, getMaxLength, getMinLength, getMaxItems, getMinItems } from "@typespec/compiler";
import { stateKeys } from "./lib.js";

export interface Condition {
  sourceName: string;
  sourceIsArray: boolean;
  value: string | number | boolean | null;
}

/** Everything the emitters need about one block, read out of decorator state. */
export interface Block {
  /** A Model for object-valued blocks, a Scalar for single-value questions. */
  model: Model | Scalar;
  kind: "question" | "form";
  /** True when the block is a single value rather than an object. */
  scalar: boolean;
  id: string;
  meta: Record<string, unknown>;
  tags: string[];
  entity?: string;
  label?: string;
  doc?: string;
  sections?: Enum;
  order?: string[];
  overrides: Record<string, Record<string, unknown>>;
}

const g = (p: Program, k: symbol, t: Type) => p.stateMap(k).get(t);

export function readBlock(program: Program, model: Model | Scalar): Block | undefined {
  const q = g(program, stateKeys.questionMeta, model) as Record<string, unknown> | undefined;
  const f = g(program, stateKeys.formMeta, model) as Record<string, unknown> | undefined;
  if (!q && !f) return undefined;
  const meta = (q ?? f)!;
  return {
    model,
    kind: q ? "question" : "form",
    scalar: model.kind === "Scalar",
    id: String(meta.id),
    meta,
    tags: (g(program, stateKeys.tags, model) as string[]) ?? [],
    entity: g(program, stateKeys.entity, model) as string | undefined,
    label: g(program, stateKeys.label, model) as string | undefined,
    doc: getDoc(program, model),
    sections: g(program, stateKeys.sections, model) as Enum | undefined,
    order: g(program, stateKeys.order, model) as string[] | undefined,
    overrides: (g(program, stateKeys.overrides, model) as Record<string, Record<string, unknown>>) ?? {},
  };
}

/** All blocks in the program, in declaration order. */
export function allBlocks(program: Program): Block[] {
  const out: Block[] = [];
  const seen = new Set<Model | Scalar>();
  const walk = (ns: any): void => {
    for (const m of [...ns.models.values(), ...ns.scalars.values()]) {
      if (seen.has(m)) continue;
      seen.add(m);
      const b = readBlock(program, m);
      if (b) out.push(b);
    }
    for (const child of ns.namespaces.values()) walk(child);
  };
  walk(program.getGlobalNamespaceType());
  return out;
}

export const propLabel = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.label, prop) as string | undefined;
export const propHelpText = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.helpText, prop) as string | undefined;
export const propWidget = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.widget, prop) as string | undefined;
export const propSection = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.section, prop) as { name: string; label?: string } | undefined;
export const propReadOnly = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.readOnly, prop) === true;
export const propReadOnlyWhen = (p: Program, prop: ModelProperty) =>
  (g(p, stateKeys.readOnlyWhen, prop) as Condition[]) ?? [];
export const propOmit = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.omit, prop) === true;
export const propVisibleWhen = (p: Program, prop: ModelProperty) =>
  (g(p, stateKeys.visibleWhen, prop) as Condition[]) ?? [];
export const propRequiredWhen = (p: Program, prop: ModelProperty) =>
  (g(p, stateKeys.requiredWhen, prop) as Condition[]) ?? [];
export const propComputed = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.computed, prop) as { operator: string; refs: string[] } | undefined;
export const propTotals = (p: Program, prop: ModelProperty) =>
  g(p, stateKeys.totals, prop) as ModelProperty[] | undefined;
/** `@Sgg.prePopulate`: canonical data path -> SGG rule name, declared on the form. */
export const modelPrePopulate = (p: Program, model: Model) =>
  (g(p, stateKeys.prePopulate, model) as Record<string, string> | undefined) ?? {};
/** `@UI.label` for any model, block or not. */
export const modelLabel = (p: Program, model: Model) =>
  g(p, stateKeys.label, model) as string | undefined;
/** `@UI.order` for any model, block or not. */
export const modelOrder = (p: Program, model: Model) =>
  g(p, stateKeys.order, model) as string[] | undefined;

/** `@Sgg.multiField` declarations on a form, in the order they were written. */
export const modelMultiFields = (p: Program, model: Model) =>
  (g(p, stateKeys.multiField, model) as { section: string; widget: string }[] | undefined) ??
  [];

export const propOverrides = (p: Program, prop: ModelProperty) =>
  (g(p, stateKeys.overrides, prop) as Record<string, Record<string, unknown>>) ?? {};

/** Properties in @UI.order if given, else declaration order; omitted ones dropped. */
export function orderedProps(program: Program, block: Block): ModelProperty[] {
  if (block.model.kind !== "Model") return [];
  const props = [...block.model.properties.values()].filter((p) => !propOmit(program, p));
  if (!block.order) return props;
  const byName = new Map(props.map((p) => [p.name, p]));
  const out = block.order.map((n) => byName.get(n)).filter(Boolean) as ModelProperty[];
  for (const p of props) if (!out.includes(p)) out.push(p);
  return out;
}

/** The child block a property composes, if any. */
export function childBlock(program: Program, prop: ModelProperty): Block | undefined {
  const t = prop.type;
  if (t.kind === "Model" || t.kind === "Scalar") return readBlock(program, t);
  return undefined;
}

export function scalarConstraints(program: Program, prop: ModelProperty): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const min = getMinLength(program, prop), max = getMaxLength(program, prop);
  if (min !== undefined) out.minLength = min;
  if (max !== undefined) out.maxLength = max;
  const mnI = getMinItems(program, prop), mxI = getMaxItems(program, prop);
  if (mnI !== undefined) out.minItems = mnI;
  if (mxI !== undefined) out.maxItems = mxI;
  return out;
}

export function enumValues(e: Enum): (string | number)[] {
  return [...e.members.values()].map((m) => (m.value ?? m.name) as string | number);
}

export function scalarType(s: Scalar): string {
  let cur: Scalar | undefined = s;
  while (cur) {
    if (["string", "url", "uuid"].includes(cur.name)) return "string";
    if (["boolean"].includes(cur.name)) return "boolean";
    if (["int8","int16","int32","int64","integer","safeint"].includes(cur.name)) return "integer";
    if (["float","float32","float64","decimal","decimal128","numeric"].includes(cur.name)) return "number";
    cur = cur.baseScalar;
  }
  return "string";
}
