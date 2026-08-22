import type { Model, ModelProperty, Program } from "@typespec/compiler";
import { getDoc } from "@typespec/compiler";
import {
  Block, childBlock, modelOrder, orderedProps, propHelpText, propLabel, propOmit,
  propReadOnly, propSection, propWidget, modelLabel,
} from "../model.js";

export interface SggField {
  type: "field" | "null";
  definition: string;
  widget?: string;
}
export interface SggFieldList {
  type: "fieldList";
  name: string;
  label: string;
  description?: string;
  children: SggField[];
}
export interface SggSection {
  type: "section";
  name: string;
  label: string;
  description?: string;
  children: (SggField | SggFieldList)[];
}

const snake = (s: string) => s.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();

/**
 * Every property of a model including those inherited through `extends`, in
 * `@UI.order` if the model declares one. `@UI.order` accepts inherited properties,
 * which is what lets a form-local extension interleave its own fields with the
 * question's.
 */
function allProperties(program: Program, model: Model): ModelProperty[] {
  const chain: Model[] = [];
  for (let m: Model | undefined = model; m; m = m.baseModel) chain.unshift(m);
  const props: ModelProperty[] = [];
  for (const m of chain) props.push(...m.properties.values());

  const order = modelOrder(program, model);
  if (!order) return props;
  const byName = new Map(props.map((p) => [p.name, p]));
  const out = order.map((n) => byName.get(n)).filter(Boolean) as ModelProperty[];
  for (const p of props) if (!out.includes(p)) out.push(p);
  return out;
}

/** One form's overrides on the questions it composes, keyed by data path. */
type Overrides = Record<string, Record<string, unknown>>;

const at = (overrides: Overrides, dataPath: string) => overrides[dataPath] ?? {};

/**
 * Flatten a subtree into SGG's max-depth-1 vocabulary. A target-specific projection
 * of the canonical tree, not a composition semantic.
 *
 * `dataPath` is the dotted path an override addresses, so a form can drop or relabel one
 * field of a question it composes without the question or any other form noticing.
 */
function walk(
  program: Program,
  model: Model,
  prefix: string,
  dataPath: string,
  into: SggField[],
  overrides: Overrides,
): void {
  for (const prop of allProperties(program, model)) {
    const here = dataPath ? `${dataPath}.${prop.name}` : prop.name;
    if (propOmit(program, prop) || at(overrides, here).omit === true) continue;

    const path = `${prefix}/properties/${snake(prop.name)}`;
    const child = childBlock(program, prop);
    if (child && !child.scalar && child.model.kind === "Model") {
      walk(program, child.model, path, here, into, overrides);
      continue;
    }
    if (!child && prop.type.kind === "Model" && !prop.type.indexer) {
      walk(program, prop.type, path, here, into, overrides);
      continue;
    }
    into.push(field(program, prop, path, at(overrides, here)));
  }
}

function field(
  program: Program,
  prop: ModelProperty,
  definition: string,
  override: Record<string, unknown>,
): SggField {
  const f: SggField = {
    type: override.readOnly === true || propReadOnly(program, prop) ? "null" : "field",
    definition,
  };
  const widget = (override.widget as string | undefined) ?? propWidget(program, prop);
  if (widget) f.widget = widget;
  return f;
}

/** A model's own `@UI.label`, whether or not it is a published block. */
function itemLabel(program: Program, item: Model): string | undefined {
  return modelLabel(program, item);
}

/** An array of objects becomes a repeatable fieldList (D8: inferred, not declared). */
function asFieldList(
  program: Program,
  prop: ModelProperty,
  overrides: Overrides,
): SggFieldList | undefined {
  const t = prop.type;
  if (t.kind !== "Model" || !t.indexer) return undefined;
  const item = t.indexer.value;
  if (item.kind !== "Model") return undefined;

  const children: SggField[] = [];
  walk(program, item, `/properties/${snake(prop.name)}/items`, prop.name, children, overrides);
  // The list's label names one entry, so it comes from the item block; the property's
  // own label names the collection and stays on the schema as `title`.
  const list: SggFieldList = {
    type: "fieldList",
    name: snake(prop.name),
    label: itemLabel(program, item) ?? propLabel(program, prop) ?? prop.name,
    children,
  };
  const description = propHelpText(program, prop) ?? getDoc(program, prop);
  if (description) list.description = description;
  return list;
}

export function emitSggUi(program: Program, block: Block): SggSection[] {
  if (!block.sections || block.model.kind !== "Model") return [];

  const bySection = new Map<string, (SggField | SggFieldList)[]>();
  const meta = new Map<string, { label: string; description?: string }>();
  for (const m of block.sections.members.values()) {
    const name = snake(m.name);
    bySection.set(name, []);
    meta.set(name, { label: String(m.value ?? m.name), description: getDoc(program, m) });
  }

  const overrides = block.overrides as Overrides;
  for (const prop of orderedProps(program, block)) {
    const sec = propSection(program, prop);
    if (!sec) continue;
    const bucket = bySection.get(snake(sec.name));
    if (!bucket) continue;
    if (at(overrides, prop.name).omit === true) continue;

    const list = asFieldList(program, prop, overrides);
    if (list) { bucket.push(list); continue; }

    const path = `/properties/${snake(prop.name)}`;
    const child = childBlock(program, prop);
    if (child && !child.scalar && child.model.kind === "Model") {
      const flat: SggField[] = [];
      walk(program, child.model, path, prop.name, flat, overrides);
      bucket.push(...flat);
      continue;
    }
    bucket.push(field(program, prop, path, at(overrides, prop.name)));
  }

  const out: SggSection[] = [];
  for (const [name, children] of bySection) {
    if (!children.length) continue;
    const m = meta.get(name)!;
    const section: SggSection = { type: "section", name, label: m.label, children };
    if (m.description) section.description = m.description;
    out.push(section);
  }
  return out;
}
