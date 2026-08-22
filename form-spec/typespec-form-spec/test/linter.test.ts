import { createLinterRuleTester, type LinterRuleTester } from "@typespec/compiler/testing";
import { beforeEach, describe, it } from "vitest";
import { $linter } from "../src/linter.js";
import { Tester, bank, form, formMeta } from "./tester.js";

const rule = (name: string) => {
  const found = $linter.rules.find((r) => r.name === name);
  if (!found) throw new Error(`no rule named ${name}`);
  return found;
};

async function tester(name: string): Promise<LinterRuleTester> {
  const instance = await Tester.createInstance();
  return createLinterRuleTester(instance, rule(name), "@simpler-grants/form-spec");
}

describe("no-orphan-question", () => {
  let lint: LinterRuleTester;
  beforeEach(async () => {
    lint = await tester("no-orphan-question");
  });

  it("reports a question nothing composes", async () => {
    await lint
      .expect(
        bank(`
          /** Unasked. */
          @Question.meta(#{ id: "generics/unasked" })
          @Catalog.tag(TagName.name)
          scalar Unasked extends string;
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/no-orphan-question",
      });
  });

  it("counts composition through a property", async () => {
    await lint
      .expect(
        form(`
          /** Asked. */
          @Question.meta(#{ id: "generics/asked" })
          @Catalog.tag(TagName.name)
          scalar Asked extends string;

          enum Section { only: "Only" }

          /** A form. */
          ${formMeta("asks")}
          @UI.sections(Section)
          model Asks {
            @UI.section(Section.only)
            field?: Asked;
          }
        `),
      )
      .toBeValid();
  });

  it("counts composition through `extends`", async () => {
    await lint
      .expect(
        bank(`
          /** A point of contact. */
          @Question.meta(#{ id: "poc/details" })
          @Catalog.tag(TagName.person)
          model Poc {
            name: string;
          }

          /** A form-local extension. */
          @Question.meta(#{ id: "poc/extended" })
          @Catalog.tag(TagName.person)
          model Extended extends Poc {
            role: string;
          }
        `),
      )
      .toEmitDiagnostics({
        // `poc/extended` is itself unasked; `poc/details` is not reported, because
        // extending it composes it.
        code: "@simpler-grants/form-spec/no-orphan-question",
        message: /poc\/extended/,
      });
  });

  it("counts composition reached through a model that is not a question", async () => {
    await lint
      .expect(
        form(`
          /** Quarters. */
          @Question.meta(#{ id: "budget/quarters" })
          @Catalog.tag(TagName.money)
          model Quarters {
            q1?: string;
          }

          model Wrapper {
            federal?: Quarters;
          }

          enum Section { only: "Only" }

          /** A form. */
          ${formMeta("wraps")}
          @UI.sections(Section)
          model Wraps {
            @UI.section(Section.only)
            cash?: Wrapper;
          }
        `),
      )
      .toBeValid();
  });

  it("counts composition through a list", async () => {
    await lint
      .expect(
        form(`
          /** An attachment. */
          @Question.meta(#{ id: "generics/attachment" })
          @Catalog.tag(TagName.attachment)
          scalar AttachmentRef extends string;

          enum Section { only: "Only" }

          /** A form. */
          ${formMeta("lists")}
          @UI.sections(Section)
          model Lists {
            @UI.section(Section.only)
            files?: AttachmentRef[];
          }
        `),
      )
      .toBeValid();
  });
});

describe("require-question-docs", () => {
  it("reports a question with no doc comment", async () => {
    const lint = await tester("require-question-docs");
    await lint
      .expect(
        bank(`
          @Question.meta(#{ id: "generics/undocumented" })
          @Catalog.tag(TagName.name)
          scalar Undocumented extends string;
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/require-question-docs",
      });
  });

  it("accepts one with a doc comment", async () => {
    const lint = await tester("require-question-docs");
    await lint
      .expect(
        bank(`
          /** Documented. */
          @Question.meta(#{ id: "generics/documented" })
          @Catalog.tag(TagName.name)
          scalar Documented extends string;
        `),
      )
      .toBeValid();
  });
});

describe("require-question-tags", () => {
  it("reports an untagged question", async () => {
    const lint = await tester("require-question-tags");
    await lint
      .expect(
        bank(`
          /** Untagged. */
          @Question.meta(#{ id: "generics/untagged" })
          scalar Untagged extends string;
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/require-question-tags",
      });
  });
});

describe("section-unused", () => {
  it("reports a section no field is placed in", async () => {
    const lint = await tester("section-unused");
    await lint
      .expect(
        form(`
          enum Section { used: "Used", empty: "Empty" }

          /** A form. */
          ${formMeta("half-empty")}
          @UI.sections(Section)
          model HalfEmpty {
            @UI.section(Section.used)
            field?: string;
          }
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/section-unused",
        message: /empty/,
      });
  });

  it("accepts a form whose sections are all used", async () => {
    const lint = await tester("section-unused");
    await lint
      .expect(
        form(`
          enum Section { used: "Used" }

          /** A form. */
          ${formMeta("full")}
          @UI.sections(Section)
          model Full {
            @UI.section(Section.used)
            field?: string;
          }
        `),
      )
      .toBeValid();
  });
});

describe("order-incomplete", () => {
  it("reports an order that omits a property", async () => {
    const lint = await tester("order-incomplete");
    await lint
      .expect(
        bank(`
          /** Partly ordered. */
          @Question.meta(#{ id: "generics/partial" })
          @Catalog.tag(TagName.name)
          @UI.order(Partial.b)
          model Partial {
            a?: string;
            b?: string;
          }
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/order-incomplete",
        message: /omits a/,
      });
  });

  it("accepts a complete order", async () => {
    const lint = await tester("order-incomplete");
    await lint
      .expect(
        bank(`
          /** Fully ordered. */
          @Question.meta(#{ id: "generics/complete" })
          @Catalog.tag(TagName.name)
          @UI.order(Complete.b, Complete.a)
          model Complete {
            a?: string;
            b?: string;
          }
        `),
      )
      .toBeValid();
  });
});

describe("no-redeclared-property", () => {
  it("reports a derived block re-declaring what it inherits", async () => {
    const lint = await tester("no-redeclared-property");
    await lint
      .expect(
        bank(`
          /** A base. */
          @Question.meta(#{ id: "generics/base" })
          @Catalog.tag(TagName.name)
          model Base {
            city?: string;
          }

          model Derived extends Base {
            city?: string;
          }
        `),
      )
      .toEmitDiagnostics({
        code: "@simpler-grants/form-spec/no-redeclared-property",
        message: /city/,
      });
  });

  it("accepts a derived block that only adds", async () => {
    const lint = await tester("no-redeclared-property");
    await lint
      .expect(
        bank(`
          /** A base. */
          @Question.meta(#{ id: "generics/base" })
          @Catalog.tag(TagName.name)
          model Base {
            city?: string;
          }

          model Derived extends Base {
            county?: string;
          }
        `),
      )
      .toBeValid();
  });
});
