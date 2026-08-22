import { createTester } from "@typespec/compiler/testing";
import { fileURLToPath } from "url";

/**
 * A tester rooted at this package, so `import "@simpler-grants/form-spec"` resolves the way
 * it does in a real specification.
 *
 * `@typespec/json-schema` is deliberately absent. These fixtures exercise the checks, and a
 * check runs on the type graph -- whether the graph is also being emitted as JSON Schema is
 * not part of what is under test. The emitter has its own tests.
 */
export const Tester = createTester(fileURLToPath(new URL("..", import.meta.url)), {
  libraries: ["@simpler-grants/form-spec"],
});

/** The preamble every fixture needs: the library, and a namespace to declare blocks in. */
export const bank = (body: string) => `
  import "@simpler-grants/form-spec";
  using SimplerForms;
  namespace QuestionBank {
    ${body}
  }
`;

export const form = (body: string) => `
  import "@simpler-grants/form-spec";
  using SimplerForms;
  namespace Forms {
    ${body}
  }
`;

/** Metadata every form needs, so a fixture can say only what it is testing. */
export const formMeta = (id: string) => `@Form.meta(#{
    id: "${id}",
    formId: "00000000-0000-0000-0000-000000000000",
    formName: "${id}",
    shortFormName: "${id}",
    formVersion: "1.0",
  })`;
