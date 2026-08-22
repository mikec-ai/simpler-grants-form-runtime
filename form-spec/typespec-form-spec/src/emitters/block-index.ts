import type { Program } from "@typespec/compiler";
import { Block } from "../model.js";

/** One catalogue entry per block, mirroring the consuming site's CatalogItem. */
export function emitBlockIndex(program: Program, block: Block): Record<string, unknown> {
  return {
    id: block.id,
    kind: block.kind,
    name: block.label ?? block.id,
    description: block.doc ?? "",
    tags: block.tags,
    ...(block.entity ? { entity: block.entity } : {}),
  };
}
