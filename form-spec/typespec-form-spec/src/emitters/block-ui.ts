import type { Program } from "@typespec/compiler";
import { getDoc } from "@typespec/compiler";
import {
  Block, childBlock, orderedProps, propLabel, propReadOnly, propVisibleWhen, propWidget,
} from "../model.js";

export interface UiNode {
  type: string;
  scope?: string;
  label?: string;
  elements?: UiNode[];
  options?: Record<string, unknown>;
  rule?: Record<string, unknown>;
}

/** Re-prefix every Control scope so a child's tree sits under `propName`. */
export function rescopeUi(node: UiNode, propName: string): UiNode {
  const out: UiNode = { ...node };
  if (typeof out.scope === "string" && out.scope.startsWith("#/")) {
    out.scope = `#/properties/${propName}/${out.scope.slice(2)}`;
  }
  if (out.elements) out.elements = out.elements.map((c) => rescopeUi(c, propName));
  return out;
}

/**
 * The canonical UI artifact for one block. Scopes are relative to this block's own
 * root, so it renders standalone; children are incorporated and re-scoped.
 */
export function emitBlockUi(program: Program, block: Block): UiNode {
  // A single-value question renders as one Control at its own root.
  if (block.scalar) {
    const node: UiNode = { type: "Control", scope: "#" };
    if (block.label) node.label = block.label;
    return node;
  }

  const elements: UiNode[] = [];

  for (const prop of orderedProps(program, block)) {
    const child = childBlock(program, prop);
    if (child && !child.scalar) {
      elements.push(rescopeUi(emitBlockUi(program, child), prop.name));
      continue;
    }

    const node: UiNode = { type: "Control", scope: `#/properties/${prop.name}` };
    const label = propLabel(program, prop);
    if (label) node.label = label;

    const widget = propWidget(program, prop);
    if (widget) node.options = { ...(node.options ?? {}), widget };
    if (propReadOnly(program, prop)) node.options = { ...(node.options ?? {}), readonly: true };

    const conds = propVisibleWhen(program, prop);
    if (conds.length === 1) {
      const c = conds[0];
      node.rule = {
        effect: "SHOW",
        condition: {
          scope: `#/properties/${c.sourceName}`,
          schema: { const: c.value },
        },
      };
    }

    elements.push(node);
  }

  const group: UiNode = { type: "Group", elements };
  if (block.label) group.label = block.label;
  else if (block.doc) group.label = block.doc;
  return group;
}
