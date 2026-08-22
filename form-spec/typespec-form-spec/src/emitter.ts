import type { EmitContext } from "@typespec/compiler";
import { emitFile, resolvePath } from "@typespec/compiler";
import { $onEmit as emitJsonSchema } from "@typespec/json-schema";
import { allBlocks } from "./model.js";
import { blockSchemaRef } from "./decorators.js";
import { emitSchemaOverlay } from "./emitters/overlay.js";
import { emitBlockUi } from "./emitters/block-ui.js";
import { emitSggUi } from "./emitters/ui-schema-sgg.js";
import { emitSggRules } from "./emitters/rules-sgg.js";
import { emitBlockIndex } from "./emitters/block-index.js";

export interface FormSpecOptions {
  /**
   * Optional base URI to make `$id` and `$ref` absolute. Omitted by default: where
   * the artifacts are hosted is a per-consumer decision, and a block's identity is
   * its `@Question.meta.id`, not its URI.
   */
  "base-uri"?: string;
}

const STAGING = ".json-schema";

type Json = Record<string, any>;

/**
 * Wraps `@typespec/json-schema`: it owns every keyword derivable from the type graph,
 * this emitter owns everything derived from our decorators, and the two are composed
 * here rather than by a downstream build step.
 */
export async function $onEmit(context: EmitContext<FormSpecOptions>): Promise<void> {
  const program = context.program;
  if (program.compilerOptions.noEmit) return;

  const outDir = context.emitterOutputDir;
  const stagingDir = resolvePath(outDir, STAGING);

  // 1. Let the stock emitter produce the base schemas into a staging directory.
  await emitJsonSchema({
    ...context,
    emitterOutputDir: stagingDir,
    options: { "file-type": "json" },
  } as any);

  // 2. Read them back and index by $id and by file name.
  const byId = new Map<string, Json>();
  const byFile = new Map<string, Json>();
  for (const name of await listJson(program, stagingDir)) {
    const raw = await program.host.readFile(resolvePath(stagingDir, name));
    const doc = JSON.parse(raw.text) as Json;
    byFile.set(name, doc);
    if (doc.$id) byId.set(doc.$id, doc);
  }

  const baseUri = context.options?.["base-uri"];
  const write = (rel: string, value: unknown) =>
    emitFile(program, {
      path: resolvePath(outDir, rel),
      content: JSON.stringify(value, null, 2) + "\n",
    });

  const blocks = allBlocks(program);
  const refToDir = new Map(
    blocks.map((b) => [
      blockSchemaRef(b.id),
      b.kind === "question" ? `question-bank/${b.id}` : `forms/${b.id}`,
    ]),
  );

  for (const block of blocks) {
    const dir = refToDir.get(blockSchemaRef(block.id))!;
    const stock = byId.get(blockSchemaRef(block.id));
    if (!stock) continue;

    // 3. Inline refs to unpublished declarations into $defs, as the goldens do.
    const defs: Json = {};
    let schema = resolveRefs(stock, { byFile, refToDir, defs, baseUri, from: dir });
    if (Object.keys(defs).length) schema = { ...schema, $defs: defs };

    // 4. Fold in the conditional requiredness only we can know about.
    const overlay = emitSchemaOverlay(program, block);
    if (overlay) schema = mergeSchema(schema, overlay);

    await write(`${dir}/schema.json`, schema);
    await write(`${dir}/ui.json`, emitBlockUi(program, block));
    await write(`${dir}/index.json`, emitBlockIndex(program, block));

    if (block.kind === "form") {
      await write(`${dir}/sgg/ui-schema.json`, emitSggUi(program, block));
      const rules = emitSggRules(program, block);
      await write(`${dir}/sgg/rule-schema.json`, Object.keys(rules).length ? rules : null);
      await write(`${dir}/manifest.json`, {
        contract: "resolved-form-package/v1",
        form: block.meta,
        artifacts: {
          "schema.json": "generated",
          "ui.json": "generated",
          "sgg/ui-schema.json": "generated",
          "sgg/rule-schema.json": "generated",
        },
      });
    }
  }
}

async function listJson(program: any, dir: string): Promise<string[]> {
  try {
    const entries = await program.host.readDir(dir);
    return entries.filter((e: string) => e.endsWith(".json"));
  } catch {
    return [];
  }
}

interface RefCtx {
  byFile: Map<string, Json>;
  refToDir: Map<string, string>;
  defs: Json;
  baseUri?: string;
  from: string;
}

/** Rewrite every `$ref`: published blocks keep their identity, others become `$defs`. */
function resolveRefs(node: any, ctx: RefCtx, seen = new Set<string>()): any {
  if (Array.isArray(node)) return node.map((n) => resolveRefs(n, ctx, seen));
  if (!node || typeof node !== "object") return node;

  const out: Json = {};
  for (const [k, v] of Object.entries(node)) {
    if (k === "$ref" && typeof v === "string" && !v.startsWith("#")) {
      if (ctx.refToDir.has(v)) {
        out[k] = ctx.baseUri ? `${ctx.baseUri.replace(/\/$/, "")}/${v}` : relativeRef(ctx.from, v, ctx);
        continue;
      }
      const target = ctx.byFile.get(v);
      if (!target) { out[k] = v; continue; }
      const name = v.replace(/\.json$/, "").split("/").pop()!;
      if (!seen.has(name)) {
        seen.add(name);
        const { $schema, $id, ...body } = target;
        ctx.defs[name] = resolveRefs(body, ctx, seen);
      }
      out[k] = `#/$defs/${name}`;
      continue;
    }
    if (k === "$id" && typeof v === "string" && ctx.baseUri) {
      out[k] = `${ctx.baseUri.replace(/\/$/, "")}/${v}`;
      continue;
    }
    out[k] = resolveRefs(v, ctx, seen);
  }
  return out;
}

/** A path from one block's directory to another's schema, for base-less artifacts. */
function relativeRef(fromDir: string, ref: string, ctx: RefCtx): string {
  const toDir = ctx.refToDir.get(ref)!;
  const up = fromDir.split("/").map(() => "..").join("/");
  return `${up}/${toDir}/schema.json`;
}

/**
 * Fold the overlay over the stock schema.
 *
 * `allOf` appends, because both sides contribute branches. `properties` merges one level
 * down, because the overlay patches individual properties and replacing the map wholesale
 * would delete every property it did not mention. Anything else the overlay states, it
 * states outright.
 */
function mergeSchema(a: Json, b: Json): Json {
  const out = { ...a };
  for (const [key, value] of Object.entries(b)) {
    if (key === "allOf" && Array.isArray(out.allOf)) {
      out.allOf = [...out.allOf, ...value];
    } else if (key === "properties" && isObject(out.properties) && isObject(value)) {
      out.properties = { ...out.properties };
      for (const [name, patch] of Object.entries(value as Json)) {
        const existing = out.properties[name];
        out.properties[name] = isObject(existing)
          ? mergeSchema(existing as Json, patch as Json)
          : patch;
      }
    } else {
      out[key] = value;
    }
  }
  return out;
}

const isObject = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);
