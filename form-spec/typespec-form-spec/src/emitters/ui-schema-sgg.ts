import type { Model, ModelProperty, Program } from "@typespec/compiler";
import { getDoc } from "@typespec/compiler";
import {
  Block, childBlock, modelLabel, modelMultiFields, modelOrder, orderedProps, propHelpText,
  propLabel, propOmit, propReadOnly, propSection, propTotals, propWidget,
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
export interface SggMultiField {
  type: "multiField";
  name: string;
  widget: string;
  definition: string[];
}
export interface SggSection {
  type: "section";
  name: string;
  label: string;
  description?: string;
  children: (SggField | SggFieldList | SggMultiField)[];
}

const snake = (s: string) => s.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();

/**
 * A section's name is a wire identifier rather than a field name, and SGG's forms do not
 * agree on a convention for it: most are snake-cased, SF-424A's are `SectionA`. So a
 * lowerCamel member name is a canonical name and gets projected, while a member written in
 * any other convention is being written in the wire's convention on purpose and is left
 * alone.
 */
const sectionName = (s: string) => (/^[a-z]/.test(s) ? snake(s) : s);

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

/**
 * The properties one of SGG's section components reads.
 *
 * Its own section's properties, plus whatever those total. Sections B, C and E each render
 * a grid over the same repeatable list that the applicant edits in section A, and the
 * list is named nowhere in their declarations -- but each section's total says which
 * collection it totals, and that is the same fact. So the column source is read off
 * `@Validation.totals` rather than repeated per section.
 */
function gridProperties(program: Program, block: Block, members: ModelProperty[]): string[] {
  const names: string[] = [];
  const add = (name: string) => {
    if (!names.includes(name)) names.push(name);
  };
  for (const member of members) {
    for (const source of propTotals(program, member) ?? []) {
      if (source.model === block.model) add(source.name);
    }
  }
  for (const member of members) add(member.name);
  return names;
}

export function emitSggUi(program: Program, block: Block): SggSection[] {
  if (!block.sections || block.model.kind !== "Model") return [];

  const order: string[] = [];
  const bySection = new Map<string, (SggField | SggFieldList | SggMultiField)[]>();
  const meta = new Map<string, { label: string; description?: string }>();
  for (const m of block.sections.members.values()) {
    const name = sectionName(m.name);
    order.push(name);
    bySection.set(name, []);
    meta.set(name, { label: String(m.value ?? m.name), description: getDoc(program, m) });
  }

  // Which properties land in each section, in order. This is the whole content of a
  // section, whether it is rendered as a field list or handed to one component.
  const props = new Map<string, ModelProperty[]>(order.map((name) => [name, []]));
  const overrides = block.overrides as Overrides;
  for (const prop of orderedProps(program, block)) {
    const sec = propSection(program, prop);
    if (!sec) continue;
    if (at(overrides, prop.name).omit === true) continue;
    props.get(sectionName(sec.name))?.push(prop);
  }

  const widgets = new Map(
    modelMultiFields(program, block.model as Model).map((d) => [sectionName(d.section), d.widget]),
  );

  for (const name of order) {
    const bucket = bySection.get(name)!;
    const members = props.get(name)!;

    // A section handed to one of SGG's components receives its properties and lays itself
    // out, so none of its fields are walked.
    const widget = widgets.get(name);
    if (widget) {
      if (!members.length) continue;
      bucket.push({
        type: "multiField",
        name: widget,
        widget,
        definition: gridProperties(program, block, members).map(
          (p) => `/properties/${snake(p)}`,
        ),
      });
      continue;
    }

    for (const prop of members) {
      const list = asFieldList(program, prop, overrides);
      if (list) {
        bucket.push(list);
        continue;
      }
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
  }

  const out: SggSection[] = [];
  for (const name of order) {
    const children = bySection.get(name)!;
    if (!children.length) continue;
    const m = meta.get(name)!;
    const section: SggSection = { type: "section", name, label: m.label, children };
    if (m.description) section.description = m.description;
    out.push(section);
  }
  return out;
}
