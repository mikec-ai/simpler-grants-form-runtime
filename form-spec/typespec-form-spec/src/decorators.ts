import type { DecoratorContext, Enum, EnumMember, Model, ModelProperty, Type } from "@typespec/compiler";
import { stateKeys } from "./lib.js";

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

export const $questionMeta = (ctx: Ctx, target: Model, meta: unknown) =>
  set(ctx, stateKeys.questionMeta, target, meta);

export const $formMeta = (ctx: Ctx, target: Model, meta: unknown) =>
  set(ctx, stateKeys.formMeta, target, meta);

// --- catalogue ------------------------------------------------------------

export const $tag = (ctx: Ctx, target: Model, ...tags: string[]) =>
  set(ctx, stateKeys.tags, target, tags);

export const $entity = (ctx: Ctx, target: Model, entity: string) =>
  set(ctx, stateKeys.entity, target, entity);

// --- presentation ---------------------------------------------------------

export const $sections = (ctx: Ctx, target: Model, sections: Enum) =>
  set(ctx, stateKeys.sections, target, sections);

export const $section = (ctx: Ctx, target: ModelProperty, section: EnumMember) =>
  set(ctx, stateKeys.section, target, section);

export const $overrides = (ctx: Ctx, target: Model | ModelProperty, patch: unknown) =>
  set(ctx, stateKeys.overrides, target, patch);

export const $label = (ctx: Ctx, target: Model | ModelProperty, text: string) =>
  set(ctx, stateKeys.label, target, text);

export const $helpText = (ctx: Ctx, target: ModelProperty, text: string) =>
  set(ctx, stateKeys.label, target, text);

export const $widget = (ctx: Ctx, target: ModelProperty, widget: string) =>
  set(ctx, stateKeys.widget, target, widget);

export const $order = (ctx: Ctx, target: Model, ...props: ModelProperty[]) =>
  set(ctx, stateKeys.order, target, props.map((p) => p.name));

export const $omit = (ctx: Ctx, target: ModelProperty) =>
  set(ctx, stateKeys.omit, target, true);

export const $readOnly = (ctx: Ctx, target: ModelProperty) =>
  set(ctx, stateKeys.readOnly, target, true);

// --- conditional logic ----------------------------------------------------

/** SPIKE 1: `source` is a ModelProperty passed as `Model.prop` at the call site. */
export const $visibleWhen = (
  ctx: Ctx,
  target: ModelProperty,
  source: ModelProperty,
  equals: unknown,
) => push(ctx, stateKeys.visibleWhen, target, { source, equals });

export const $readOnlyWhen = (
  ctx: Ctx,
  target: ModelProperty,
  source: ModelProperty,
  equals: unknown,
) => push(ctx, stateKeys.readOnly, target, { source, equals });

export const $requiredWhen = (
  ctx: Ctx,
  target: ModelProperty,
  source: ModelProperty,
  equals: unknown,
) => push(ctx, stateKeys.requiredWhen, target, { source, equals });

export const $computed = (
  ctx: Ctx,
  target: ModelProperty,
  operator: string,
  ...refs: ModelProperty[]
) => set(ctx, stateKeys.computed, target, { operator, refs: refs.map((r) => r.name) });

// --- SGG target vocabulary ------------------------------------------------

export const $prePopulate = (ctx: Ctx, target: ModelProperty, rule: string) =>
  set(ctx, stateKeys.prePopulate, target, rule);
