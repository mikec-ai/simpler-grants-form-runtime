import Ajv2020, { type ValidateFunction } from "ajv/dist/2020.js";
import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const contractRoot = resolve(packageRoot, "contract/v1");
const emittedQuestionsRoot = resolve(packageRoot, "dist/question-bank");

async function json(path: string): Promise<unknown> {
  return JSON.parse(await readFile(path, "utf8"));
}

async function schemaArtifacts(root: string): Promise<string[]> {
  const found: string[] = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) found.push(...(await schemaArtifacts(path)));
    if (entry.isFile() && entry.name === "schema.json") found.push(path);
  }
  return found;
}

describe("artifact contract v1", () => {
  let validateQuestion: ValidateFunction;

  beforeAll(async () => {
    const ajv = new Ajv2020({ allErrors: true, strict: true });
    validateQuestion = ajv.compile(
      await json(resolve(contractRoot, "question.schema.json")),
    );
  });

  it("accepts a hand-authored question artifact without TypeSpec", async () => {
    const fixture = await json(
      resolve(contractRoot, "conformance/question.valid.json"),
    );

    expect(validateQuestion(fixture), JSON.stringify(validateQuestion.errors)).toBe(
      true,
    );
  });

  it("rejects an otherwise valid schema without portable question identity", async () => {
    const fixture = await json(
      resolve(contractRoot, "conformance/question.invalid.json"),
    );

    expect(validateQuestion(fixture)).toBe(false);
    expect(validateQuestion.errors).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ keyword: "required", params: { missingProperty: "$id" } }),
      ]),
    );
  });

  it("accepts every emitted question schema through the same artifact contract", async () => {
    const artifacts = await schemaArtifacts(emittedQuestionsRoot);

    expect(artifacts.length).toBeGreaterThan(0);
    for (const artifact of artifacts) {
      const candidate = await json(artifact);
      expect(
        validateQuestion(candidate),
        `${artifact}: ${JSON.stringify(validateQuestion.errors)}`,
      ).toBe(true);
    }
  });
});
