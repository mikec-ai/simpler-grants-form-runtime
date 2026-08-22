import type {
  DecoratorContext, Enum, EnumMember, Model, ModelProperty, Scalar, Type, Value,
} from "@typespec/compiler";
import { serializeValueAsJson, $summary } from "@typespec/compiler";
import { $id as $jsonSchemaId } from "@typespec/json-schema";
import { stateKeys } from "./lib.js";

/**
 * `valueof <Model>` arrives as a TypeSpec ObjectValue with parent back-references,
 * so it cannot be serialized directly. Convert to plain JS at the boundary.
 */
function plain(ctx: DecoratorContext, value: unknown): unknown {
  const v = value as Value;
  if (v && typeof v === "object" && "entityKind" in v && (v as any).entityKind === "Value") {
    return serializeValueAsJson(ctx.program, v, (v as any).type);
  }
  return value;
}

type Ctx = DecoratorContext;

/** Store a single value keyed by target. */
function set(ctx: Ctx, key: symbol, target: Type, value: unknown): void {
  ctx.program.stateMap(key).set(target, value);
}

/** Append to a list keyed by target. */
function push(ctx: Ctx, key: symbol, target: Type, value: unknown): void {
  const map = ctx.program.stateMap(key);
  const existing = (map.get(target) as unknown[] | undefined) ?? [];
  existing.push(value);
  map.set(target, existing);
}

// --- identity -------------------------------------------------------------

/**
 * A block's `$id`, relative to the bank's base URI. The base is declared once with
 * `@jsonSchema("<base>")` on the bank namespace, so it is a publishing decision in
 * the specs rather than a constant in this library — mirroring
 * `SharedSchemaConfig.shared_schema_base_uri` on the Python side.
 */
export const blockSchemaRef = (id: string) => `${id}/schema.json`;

/**
 * Delegate to the stock JSON Schema library, which resolves this relative id
 * against the namespace base and uses it for both `$id` and every `$ref` target.
 */
function publishAs(ctx: Ctx, target: Model | Scalar, id: string): void {
  $jsonSchemaId(ctx as any, target as any, blockSchemaRef(id));
}

export const $questionMeta = (ctx: Ctx, target: Model | Scalar, meta: unknown) => {
  const m = plain(ctx, meta) as { id: string };
  set(ctx, stateKeys.questionMeta, target, m);
  publishAs(ctx, target, m.id);
};

export const $formMeta = (ctx: Ctx, target: Model, meta: unknown) => {
  const m = plain(ctx, meta) as { id: string };
  set(ctx, stateKeys.formMeta, target, m);
  publishAs(ctx, target, m.id);
};

// --- catalogue ------------------------------------------------------------

export const $tag = (ctx: Ctx, target: Model | Scalar, ...tags: unknown[]) =>
  set(ctx, stateKeys.tags, target, tags.map((t) => enumName(t)));

export const $entity = (ctx: Ctx, target: Model | Scalar, entity: unknown) =>
  set(ctx, stateKeys.entity, target, enumName(entity));

/** An enum member argument arrives as the member; take its name. */
function enumName(v: unknown): string {
  const m = unwrap(v);
  if (m && typeof m === "object" && "name" in (m as any)) return String((m as any).name);
  return String(m);
}

/** Peel one layer of TypeSpec value wrapping. */
function unwrap(v: unknown): unknown {
  const o = v as any;
  if (o && typeof o === "object" && "entityKind" in o && o.entityKind === "Value" && "value" in o) {
    return o.value;
  }
  return v;
}

/**
 * Resolve a decorator argument to a plain JSON literal. Enum members yield their
 * wire value, so a comparison in an emitted schema is a string rather than a
 * compiler object with parent back-references.
 */
function literal(v: unknown): string | number | boolean | null {
  const u = unwrap(v) as any;
  if (u === null || u === undefined) return null;
  if (typeof u !== "object") return u;
  if (u.kind === "EnumMember" || ("name" in u && "enum" in u)) {
    return (u.value ?? u.name) as string | number;
  }
  if ("value" in u) return literal(u.value);
  if ("name" in u) return String(u.name);
  return String(u);
}

// --- presentation ---------------------------------------------------------

export const $sections = (ctx: Ctx, target: Model, sections: Enum) =>
  set(ctx, stateKeys.sections, target, sections);

/**
 * `valueof EnumMember` arrives as a value, not the member type, so resolve the
 * member's name and label here rather than in the emitters.
 */
export const $section = (ctx: Ctx, target: ModelProperty, section: unknown) =>
  set(ctx, stateKeys.section, target, sectionRef(section));

function sectionRef(v: unknown): { name: string; label?: string } {
  const m = v as any;
  if (m && typeof m === "object") {
    if (m.name) return { name: String(m.name), label: m.value ? String(m.value) : undefined };
    if (m.value?.name) return { name: String(m.value.name), label: m.value.value ? String(m.value.value) : undefined };
  }
  return { name: String(v) };
}

export const $overrides = (ctx: Ctx, target: Model | ModelProperty, patch: unknown) =>
  set(ctx, stateKeys.overrides, target, plain(ctx, patch));

/**
 * A field label. Also delegated to `@summary`, which the JSON Schema emitter maps to
 * `title` — so the canonical schema carries the label without this library emitting
 * any schema keyword itself.
 */
export const $label = (ctx: Ctx, target: Model | Scalar | ModelProperty, text: string) => {
  set(ctx, stateKeys.label, target, text);
  $summary(ctx as any, target as any, text);
};

/**
 * Secondary guidance shown with the field. Distinct from the doc comment, which is the
 * question's own description: help text is what a form says *about asking it here*.
 */
export const $helpText = (ctx: Ctx, target: ModelProperty, text: string) =>
  set(ctx, stateKeys.helpText, target, text);

export const $widget = (ctx: Ctx, target: ModelProperty, widget: unknown) =>
  set(ctx, stateKeys.widget, target, enumName(widget));

export const $order = (ctx: Ctx, target: Model, ...props: ModelProperty[]) =>
  set(ctx, stateKeys.order, target, props.map((p) => p.name));

export const $omit = (ctx: Ctx, target: ModelProperty) =>
  set(ctx, stateKeys.omit, target, true);

export const $readOnly = (ctx: Ctx, target: ModelProperty) =>
  set(ctx, stateKeys.readOnly, target, true);

// --- conditional logic ----------------------------------------------------

/**
 * `source` is a ModelProperty passed as `Model.prop` at the call site. It is reduced
 * to plain data here so no emitter ever handles a compiler object.
 */
function condition(source: ModelProperty, equals: unknown) {
  const t = source.type as any;
  return {
    sourceName: source.name,
    sourceIsArray: t?.kind === "Model" && !!t.indexer,
    value: literal(equals),
  };
}

export const $visibleWhen = (ctx: Ctx, target: ModelProperty, source: ModelProperty, equals: unknown) =>
  push(ctx, stateKeys.visibleWhen, target, condition(source, equals));

export const $readOnlyWhen = (ctx: Ctx, target: ModelProperty, source: ModelProperty, equals: unknown) =>
  push(ctx, stateKeys.readOnlyWhen, target, condition(source, equals));

export const $requiredWhen = (ctx: Ctx, target: ModelProperty, source: ModelProperty, equals: unknown) =>
  push(ctx, stateKeys.requiredWhen, target, condition(source, equals));

export const $computed = (
  ctx: Ctx,
  target: ModelProperty,
  operator: unknown,
  ...refs: ModelProperty[]
) =>
  set(ctx, stateKeys.computed, target, {
    operator: enumName(operator),
    refs: refs.map((r) => r.name),
  });

/**
 * Field-by-field totalling. Only the source properties are recorded; which field of the
 * block pairs with which is worked out at emission, where the type graph is in view.
 */
export const $totals = (ctx: Ctx, target: ModelProperty, ...sources: ModelProperty[]) =>
  set(ctx, stateKeys.totals, target, sources);

// --- SGG target vocabulary ------------------------------------------------

/** The rule name is the enum member's *value*, which is SGG's wire spelling. */
export const $multiField = (ctx: Ctx, target: Model, section: unknown, widget: unknown) =>
  push(ctx, stateKeys.multiField, target, {
    section: sectionRef(section).name,
    widget: enumName(widget),
  });

/**
 * The rule name is each entry's enum *value*, which is SGG's wire spelling. Marshalled here
 * so the emitter sees a plain `path -> rule` map (D11).
 */
export const $prePopulate = (ctx: Ctx, target: Model, rules: unknown) => {
  const table = plain(ctx, rules) as Record<string, unknown>;
  const out: Record<string, string> = {};
  for (const [path, rule] of Object.entries(table ?? {})) {
    out[path] = String(literal(rule));
  }
  set(ctx, stateKeys.prePopulate, target, out);
};

