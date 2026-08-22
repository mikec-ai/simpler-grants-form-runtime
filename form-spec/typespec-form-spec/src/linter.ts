import type { Model, ModelProperty, Program, Scalar } from "@typespec/compiler";
import { createRule, defineCodeFix, defineLinter, getDoc, getSourceLocation, paramMessage } from "@typespec/compiler";
import { allBlocks, modelOrder, orderedProps, propOmit, propSection } from "./model.js";

/**
 * Hygiene checks. A TypeSpec linter rule may only be a warning, so everything whose failure
 * makes an artifact *wrong* lives in `$onValidate` instead; what is left here is a
 * specification worth tidying rather than a broken one.
 */

const orphanQuestion = createRule({
  name: "no-orphan-question",
  severity: "warning",
  description: "A bank question that no form and no other question composes.",
  messages: {
    default: paramMessage`Question "${"id"}" is composed by nothing. Either a form should ask it or it should be deleted; an unasked question is still maintained.`,
  },
  create(context) {
    return {
      root: (program) => {
        const blocks = allBlocks(program);
        const byType = new Map(blocks.map((block) => [block.model, block]));
        const referenced = new Set<string>();

        // Reachability, not property references. A question is composed by holding it in a
        // property, by extending it, or by being reached through a model that is not itself
        // a question -- and all three have to count, or the rule reports a question that a
        // form does ask.
        const seen = new Set<Model | Scalar>();
        const reach = (type: Model | Scalar, viaComposition: boolean): void => {
          const block = byType.get(type);
          if (block && viaComposition) referenced.add(block.id);
          if (seen.has(type)) return;
          seen.add(type);
          if (type.kind !== "Model") return;
          if (type.baseModel) reach(type.baseModel, true);
          for (const prop of type.properties.values()) {
            for (const target of held(prop)) reach(target, true);
          }
        };
        for (const block of blocks) reach(block.model, false);

        for (const block of blocks) {
          if (block.kind !== "question") continue;
          if (referenced.has(block.id)) continue;
          context.reportDiagnostic({ target: block.model, format: { id: block.id } });
        }
      },
    };
  },
});

/** The declarations a property holds: its type, or the entries of a list. */
function held(prop: ModelProperty): (Model | Scalar)[] {
  const type = prop.type;
  if (type.kind === "Scalar") return [type];
  if (type.kind !== "Model") return [];
  if (!type.indexer) return [type];
  const item = type.indexer.value;
  return item.kind === "Model" || item.kind === "Scalar" ? [item] : [];
}

const questionDocs = createRule({
  name: "require-question-docs",
  severity: "warning",
  description: "Every bank question needs a doc comment; it becomes its description.",
  messages: {
    default: paramMessage`Question "${"id"}" has no doc comment, so it has no description. Applicants read it, and so does anyone browsing the bank.`,
  },
  create(context) {
    return {
      root: (program) => {
        for (const block of allBlocks(program)) {
          if (block.kind !== "question") continue;
          if (getDoc(program, block.model)) continue;
          context.reportDiagnostic({ target: block.model, format: { id: block.id } });
        }
      },
    };
  },
});

const sectionUnused = createRule({
  name: "section-unused",
  severity: "warning",
  description: "A declared section that no field is placed in.",
  messages: {
    default: paramMessage`Section "${"section"}" on ${"form"} holds no fields, so it will not render. Usually this means a field was dropped.`,
  },
  create(context) {
    return {
      root: (program) => {
        for (const block of allBlocks(program)) {
          if (block.kind !== "form" || !block.sections || block.model.kind !== "Model") continue;
          const used = new Set<string>();
          for (const prop of orderedProps(program, block)) {
            const section = propSection(program, prop);
            if (section) used.add(section.name);
          }
          for (const member of block.sections.members.values()) {
            if (used.has(member.name)) continue;
            context.reportDiagnostic({
              target: member,
              format: { section: member.name, form: block.id },
            });
          }
        }
      },
    };
  },
});

const orderIncomplete = createRule({
  name: "order-incomplete",
  severity: "warning",
  description: "@UI.order that omits a property, which then falls to the end.",
  messages: {
    default: paramMessage`@UI.order on ${"model"} omits ${"missing"}. Omitted properties are appended in declaration order, which is rarely what was meant.`,
  },
  create(context) {
    return {
      model: (model) => {
        const order = modelOrder(context.program, model);
        if (!order) return;
        const missing = [...properties(model)]
          .filter((prop) => !propOmit(context.program, prop) && !order.includes(prop.name))
          .map((prop) => prop.name);
        if (!missing.length) return;
        context.reportDiagnostic({
          target: model,
          format: { model: model.name || "an anonymous model", missing: missing.join(", ") },
          codefixes: [appendToOrder(model, missing)],
        });
      },
    };
  },
});

/**
 * The fix is mechanical -- append the missing names in declaration order -- so it is
 * offered rather than described.
 */
function appendToOrder(model: Model, missing: string[]) {
  return defineCodeFix({
    id: "append-to-ui-order",
    label: `Append ${missing.join(", ")} to @UI.order`,
    fix: (context) => {
      const decorator = model.decorators.find((d) => d.definition?.name === "@order");
      const location = getSourceLocation(decorator?.node ?? model.node);
      if (!location) return;
      const text = location.file.text.slice(location.pos, location.end);
      const close = text.lastIndexOf(")");
      if (close < 0) return;
      const addition = missing.map((n) => `, ${model.name}.${n}`).join("");
      return context.prependText(
        { file: location.file, pos: location.pos + close, end: location.pos + close },
        addition,
      );
    },
  });
}

const redeclaredProperty = createRule({
  name: "no-redeclared-property",
  severity: "warning",
  description: "A derived block re-declaring a property it already inherits.",
  messages: {
    default: paramMessage`${"model"} re-declares ${"names"}, which it already inherits from ${"base"}. To change only the presentation use @UI.overrides; re-declaring makes a second copy of the field that the two must be kept in step by hand.`,
  },
  create(context) {
    return {
      model: (model) => {
        if (!model.baseModel) return;
        const inherited = new Set<string>();
        for (let m = model.baseModel; m; m = m.baseModel!) {
          for (const prop of m.properties.keys()) inherited.add(prop);
          if (!m.baseModel) break;
        }
        const clashes = [...model.properties.keys()].filter((n) => inherited.has(n));
        if (!clashes.length) return;
        context.reportDiagnostic({
          target: model,
          format: {
            model: model.name || "an anonymous model",
            names: clashes.join(", "),
            base: model.baseModel.name || "its base",
          },
        });
      },
    };
  },
});

const untaggedQuestion = createRule({
  name: "require-question-tags",
  severity: "warning",
  description: "A bank question with no tags cannot be found by browsing.",
  messages: {
    default: paramMessage`Question "${"id"}" has no @Catalog.tag, so it appears under no heading in the question browser.`,
  },
  create(context) {
    return {
      root: (program) => {
        for (const block of allBlocks(program)) {
          if (block.kind !== "question" || block.tags.length) continue;
          context.reportDiagnostic({ target: block.model, format: { id: block.id } });
        }
      },
    };
  },
});

/** Own and inherited properties, the derived declaration winning. */
function properties(model: Model): ModelProperty[] {
  const out = new Map<string, ModelProperty>();
  const chain: Model[] = [];
  for (let m: Model | undefined = model; m; m = m.baseModel) chain.unshift(m);
  for (const m of chain) for (const prop of m.properties.values()) out.set(prop.name, prop);
  return [...out.values()];
}

export const $linter = defineLinter({
  rules: [
    orphanQuestion,
    questionDocs,
    sectionUnused,
    orderIncomplete,
    redeclaredProperty,
    untaggedQuestion,
  ],
  ruleSets: {
    recommended: {
      enable: {
        "@simpler-grants/form-spec/no-orphan-question": true,
        "@simpler-grants/form-spec/require-question-docs": true,
        "@simpler-grants/form-spec/section-unused": true,
        "@simpler-grants/form-spec/order-incomplete": true,
        "@simpler-grants/form-spec/no-redeclared-property": true,
        "@simpler-grants/form-spec/require-question-tags": true,
      },
    },
  },
});
