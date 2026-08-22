import type {
  Enum, Model, ModelProperty, Namespace, Program, Scalar, Type,
} from "@typespec/compiler";
import { reportDiagnostic } from "./lib.js";
import {
  Block, Condition, allBlocks, childBlock, modelMultiFields, orderedProps, propComputed,
  propOmit, propPrePopulate, propReadOnlyWhen, propRequiredWhen, propSection,
  propVisibleWhen,
} from "./model.js";

/**
 * Whole-program checks whose failure means the emitted artifacts would be wrong.
 *
 * These are errors, so they run here rather than in the linter, which may only warn. Each
 * one exists because the defect it catches is currently invisible: a question named after a
 * form, two blocks colliding on one output path, a condition comparing against a value the
 * source enum does not have, a calculation that depends on itself, a field that is required
 * but can be hidden, and a field in no section.
 */
export function $onValidate(program: Program): void {
  const blocks = allBlocks(program);

  checkQuestionIds(program, blocks);
  checkDuplicateIds(program, blocks);

  for (const block of blocks) {
    if (block.model.kind !== "Model") continue;
    checkSections(program, block);
    checkOverridePaths(program, block);
    checkMultiFieldSections(program, block);
    for (const prop of block.model.properties.values()) {
      checkConditions(program, prop);
      checkRequiredButHidden(program, prop);
      if (block.kind === "question") checkNoSggInBank(program, block, prop);
    }
  }

  checkCalculationCycles(program, blocks);
}

// ---------------------------------------------------------------------------
// identity

/** Words that name a form rather than a meaning. */
const FORM_WORDS = [
  "sf424", "sf-424", "sf424a", "sf424b", "sf424c", "sf424d", "rr", "sflll", "cd511",
  "epa", "neh", "phs", "key-contacts", "key_contacts", "lobbying", "profile", "short",
];

function checkQuestionIds(program: Program, blocks: Block[]): void {
  for (const block of blocks) {
    if (block.kind !== "question") continue;
    const segments = block.id.toLowerCase().split(/[/\-_]/);
    const offender = FORM_WORDS.find(
      (word) => segments.includes(word) || block.id.toLowerCase().includes(word),
    );
    if (offender) {
      reportDiagnostic(program, {
        code: "form-scoped-question-id",
        target: block.model,
        format: { id: block.id },
      });
    }
  }
}

/**
 * Two blocks claiming one id would write to one output path, and the second would win
 * silently. The usual cause is `model X is Y`, which copies the base's decorators --
 * including its identity -- where `extends` would not.
 */
function checkDuplicateIds(program: Program, blocks: Block[]): void {
  const byId = new Map<string, Block>();
  for (const block of blocks) {
    const first = byId.get(block.id);
    if (first) {
      reportDiagnostic(program, {
        code: "duplicate-block-id",
        target: block.model,
        format: { id: block.id, first: name(first.model), second: name(block.model) },
      });
      continue;
    }
    byId.set(block.id, block);
  }
}

const name = (type: Model | Scalar) => type.name || "an anonymous model";

// ---------------------------------------------------------------------------
// conditions

/** Every condition on a property, whichever effect it drives. */
function conditionsOf(program: Program, prop: ModelProperty): Condition[] {
  return [
    ...propVisibleWhen(program, prop),
    ...propReadOnlyWhen(program, prop),
    ...propRequiredWhen(program, prop),
  ];
}

/**
 * A condition compares a source property against a literal. If the source is enumerated
 * and the literal is not one of its members, the condition can never hold -- so the field
 * it governs is permanently hidden, permanently read-only, or never required, and no test notices.
 */
function checkConditions(program: Program, prop: ModelProperty): void {
  const model = prop.model;
  if (!model) return;
  for (const condition of conditionsOf(program, prop)) {
    const source = model.properties.get(condition.sourceName);
    if (!source) continue;
    const enumeration = enumOf(source.type);
    if (!enumeration) continue;
    const members = [...enumeration.members.values()].map((m) => m.value ?? m.name);
    if (members.includes(condition.value as string | number)) continue;
    reportDiagnostic(program, {
      code: "condition-value-not-in-enum",
      target: prop,
      format: {
        value: String(condition.value),
        enumName: enumeration.name,
        members: members.slice(0, 6).join(", ") + (members.length > 6 ? ", ..." : ""),
      },
    });
  }
}

/** The enum behind a property's type, looking through an array. */
function enumOf(type: Type): Enum | undefined {
  if (type.kind === "Enum") return type;
  if (type.kind === "Model" && type.indexer) return enumOf(type.indexer.value);
  return undefined;
}

/**
 * A field that is always required but only sometimes visible is a dead end: the applicant
 * cannot submit and cannot see why. This is the check that is impossible in the shipping
 * architecture, where requiredness lives in the JSON Schema and visibility in the UI
 * schema, in different languages.
 */
function checkRequiredButHidden(program: Program, prop: ModelProperty): void {
  if (prop.optional) return;
  if (!propVisibleWhen(program, prop).length) return;
  reportDiagnostic(program, {
    code: "required-but-unreachable",
    target: prop,
    format: { name: prop.name },
  });
}

// ---------------------------------------------------------------------------
// sections and overrides

function checkSections(program: Program, block: Block): void {
  if (block.kind !== "form" || !block.sections) return;
  for (const prop of orderedProps(program, block)) {
    if (propOmit(program, prop)) continue;
    if (propSection(program, prop)) continue;
    reportDiagnostic(program, {
      code: "section-orphan",
      target: prop,
      format: { name: prop.name },
    });
  }
}

/**
 * An override addresses a field by the path an applicant's answer takes. A path that does
 * not resolve is a silently ignored override -- the CommonGrants bank's stringly-typed
 * override table, caught at compile time instead of at website build time.
 */
function checkOverridePaths(program: Program, block: Block): void {
  for (const path of Object.keys(block.overrides)) {
    const reason = resolvePath(program, block.model as Model, path.split("."));
    if (!reason) continue;
    reportDiagnostic(program, {
      code: "override-path-unresolved",
      target: block.model,
      format: { path, reason },
    });
  }
}

/** Undefined when the path resolves; otherwise why it did not. */
function resolvePath(program: Program, model: Model, steps: string[]): string | undefined {
  let current: Model | undefined = model;
  for (const [index, step] of steps.entries()) {
    if (!current) return `${steps.slice(0, index).join(".")} is not an object`;
    const prop = allProperties(current).get(step);
    if (!prop) {
      const known = [...allProperties(current).keys()].slice(0, 8).join(", ");
      return `${current.name || "the model"} has no property "${step}" (has ${known})`;
    }
    if (index === steps.length - 1) return undefined;
    current = objectBehind(program, prop);
  }
  return undefined;
}

/** Own and inherited properties, the derived declaration winning. */
function allProperties(model: Model): Map<string, ModelProperty> {
  const out = new Map<string, ModelProperty>();
  const chain: Model[] = [];
  for (let m: Model | undefined = model; m; m = m.baseModel) chain.unshift(m);
  for (const m of chain) for (const prop of m.properties.values()) out.set(prop.name, prop);
  return out;
}

/** The object a property holds, whether directly or as the entries of a list. */
function objectBehind(program: Program, prop: ModelProperty): Model | undefined {
  const type = prop.type;
  if (type.kind !== "Model") return undefined;
  if (type.indexer) {
    const item = type.indexer.value;
    return item.kind === "Model" ? item : undefined;
  }
  const block = childBlock(program, prop);
  if (block && block.scalar) return undefined;
  return type;
}

/** A widget declaration naming a section the form does not have would render nothing. */
function checkMultiFieldSections(program: Program, block: Block): void {
  if (!block.sections) return;
  const declared = new Set([...block.sections.members.values()].map((m) => m.name));
  for (const entry of modelMultiFields(program, block.model as Model)) {
    if (declared.has(entry.section)) continue;
    reportDiagnostic(program, {
      code: "override-path-unresolved",
      target: block.model,
      format: {
        path: entry.section,
        reason: `no such section on this form (has ${[...declared].join(", ")})`,
      },
    });
  }
}

// ---------------------------------------------------------------------------
// calculations

/**
 * A calculated value that depends on itself has no evaluation order, so `rules-sgg` would
 * emit a rule the runtime cannot satisfy. The cycle is reported once, naming the loop.
 */
function checkCalculationCycles(program: Program, blocks: Block[]): void {
  const seen = new Set<Model>();
  for (const block of blocks) {
    if (block.model.kind !== "Model") continue;
    walkModels(program, block.model, seen, (model) => {
      const edges = new Map<string, string[]>();
      for (const prop of model.properties.values()) {
        const computed = propComputed(program, prop);
        if (computed) edges.set(prop.name, computed.refs);
      }
      for (const start of edges.keys()) {
        const cycle = findCycle(start, edges);
        if (!cycle) continue;
        reportDiagnostic(program, {
          code: "calculation-cycle",
          target: model.properties.get(start)!,
          format: { cycle: cycle.join(" -> ") },
        });
        return;
      }
    });
  }
}

function findCycle(start: string, edges: Map<string, string[]>): string[] | undefined {
  const path: string[] = [];
  const onPath = new Set<string>();
  const visit = (node: string): string[] | undefined => {
    if (onPath.has(node)) return [...path.slice(path.indexOf(node)), node];
    if (!edges.has(node)) return undefined;
    path.push(node);
    onPath.add(node);
    for (const next of edges.get(node)!) {
      const found = visit(next);
      if (found) return found;
    }
    path.pop();
    onPath.delete(node);
    return undefined;
  };
  return visit(start);
}

/** Every model reachable from a block, each visited once. */
function walkModels(
  program: Program,
  model: Model,
  seen: Set<Model>,
  visit: (model: Model) => void,
): void {
  if (seen.has(model)) return;
  seen.add(model);
  visit(model);
  for (const prop of model.properties.values()) {
    const next = objectBehind(program, prop);
    if (next) walkModels(program, next, seen, visit);
  }
}

// ---------------------------------------------------------------------------
// target vocabulary

/**
 * `@Sgg.*` names one consumer's rule vocabulary. A question is shared, so a question
 * carrying it would export that consumer's choices to every form that composes it.
 */
function checkNoSggInBank(program: Program, block: Block, prop: ModelProperty): void {
  const found: string[] = [];
  if (propPrePopulate(program, prop)) found.push("prePopulate");
  if (!found.length) return;
  if (!inQuestionBank(block.model.namespace)) return;
  for (const decorator of found) {
    reportDiagnostic(program, {
      code: "sgg-outside-forms",
      target: prop,
      format: { decorator, name: `${name(block.model)}.${prop.name}` },
    });
  }
}

function inQuestionBank(namespace: Namespace | undefined): boolean {
  for (let ns = namespace; ns; ns = ns.namespace) {
    if (ns.name === "QuestionBank") return true;
  }
  return false;
}

/** The emitter needs the same notion of "all properties", derived declaration winning. */
export { allProperties as inheritedProperties };
