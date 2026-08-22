import type { Model, ModelProperty, Program } from "@typespec/compiler";
import { getDoc } from "@typespec/compiler";
import {
  Block, childBlock, modelOrder, orderedProps, propLabel, propReadOnly, propSection,
  propWidget,
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

/**
 * Flatten a subtree into SGG's max-depth-1 vocabulary. A target-specific projection
 * of the canonical tree, not a composition semantic.
 */
function walk(program: Program, model: Model, prefix: string, into: SggField[]): void {
  for (const prop of allProperties(program, model)) {
    const path = `${prefix}/properties/${snake(prop.name)}`;
    const child = childBlock(program, prop);
    if (child && !child.scalar && child.model.kind === "Model") {
      walk(program, child.model, path, into);
      continue;
    }
    if (!child && prop.type.kind === "Model" && !prop.type.indexer) {
      walk(program, prop.type, path, into);
      continue;
    }
    into.push(field(program, prop, path));
  }
}

function field(program: Program, prop: ModelProperty, definition: string): SggField {
  const f: SggField = {
    type: propReadOnly(program, prop) ? "null" : "field",
    definition,
  };
  const widget = propWidget(program, prop);
  if (widget) f.widget = widget;
  return f;
}

/** An array of objects becomes a repeatable fieldList (D8: inferred, not declared). */
function asFieldList(
  program: Program,
  prop: ModelProperty,
): SggFieldList | undefined {
  const t = prop.type;
  if (t.kind !== "Model" || !t.indexer) return undefined;
  const item = t.indexer.value;
  if (item.kind !== "Model") return undefined;

  const children: SggField[] = [];
  walk(program, item, `/properties/${snake(prop.name)}/items`, children);
  const list: SggFieldList = {
    type: "fieldList",
    name: snake(prop.name),
    label: propLabel(program, prop) ?? prop.name,
    children,
  };
  const doc = getDoc(program, prop);
  if (doc) list.description = doc;
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

  for (const prop of orderedProps(program, block)) {
    const sec = propSection(program, prop);
    if (!sec) continue;
    const bucket = bySection.get(snake(sec.name));
    if (!bucket) continue;

    const list = asFieldList(program, prop);
    if (list) { bucket.push(list); continue; }

    const path = `/properties/${snake(prop.name)}`;
    const child = childBlock(program, prop);
    if (child && !child.scalar && child.model.kind === "Model") {
      const flat: SggField[] = [];
      walk(program, child.model, path, flat);
      bucket.push(...flat);
      continue;
    }
    bucket.push(field(program, prop, path));
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
