import fs from "node:fs";
import path from "node:path";

import {
  evaluateClientCalculations,
  hasClientCalculationRules,
} from "./clientCalculationRules";

type ConformanceCase = {
  name: string;
  input: Record<string, unknown>;
  rule_schema: Record<string, unknown>;
  expected: Record<string, unknown>;
  expected_client_errors?: string[];
};

const conformanceCases = JSON.parse(
  fs.readFileSync(
    path.resolve(
      process.cwd(),
      "../api/tests/fixtures/form_calculation_conformance.json",
    ),
    "utf8",
  ),
) as ConformanceCase[];

describe("evaluateClientCalculations", () => {
  it.each(conformanceCases)(
    "matches the server: $name",
    ({ input, rule_schema, expected, expected_client_errors }) => {
      const result = evaluateClientCalculations(input, rule_schema);
      expect(result.formData).toEqual(expected);
      expect(result.errors).toEqual(expected_client_errors ?? []);
    },
  );

  it("does not mutate the supplied form data", () => {
    const input = { a: "1.00", b: "2.00" };
    evaluateClientCalculations(input, {
      total: {
        gg_pre_population: {
          rule: "sum_monetary",
          fields: ["a", "b"],
        },
      },
    });
    expect(input).toEqual({ a: "1.00", b: "2.00" });
  });

  it("reports malformed calculation rules without changing their targets", () => {
    const result = evaluateClientCalculations(
      { total: "9.00" },
      {
        total: {
          gg_pre_population: {
            rule: "sum_monetary",
            fields: "not-an-array",
          },
        },
      },
    );
    expect(result.formData).toEqual({ total: "9.00" });
    expect(result.errors).toEqual(["Unable to evaluate sum_monetary at total"]);
  });

  it("ignores non-calculation pre-population rules", () => {
    const result = evaluateClientCalculations(
      {},
      {
        opportunity_number: {
          gg_pre_population: { rule: "opportunity_number" },
        },
      },
    );
    expect(result).toEqual({ formData: {}, errors: [] });
  });

  it("detects only supported browser calculation rules", () => {
    expect(hasClientCalculationRules(null)).toBe(false);
    expect(
      hasClientCalculationRules({
        signature: { gg_post_population: { rule: "signature" } },
      }),
    ).toBe(false);
    expect(
      hasClientCalculationRules({
        nested: {
          total: {
            gg_pre_population: { rule: "sum_monetary", fields: [] },
          },
        },
      }),
    ).toBe(true);
  });
});
