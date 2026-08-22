import type { ConditionalUiPredicate } from "src/types/applyForm/conditionalUiTypes";

import {
  evaluateConditionalUiPredicate,
  filterVisibleUiSchema,
  resolveConditionalUiState,
} from "./evaluateConditionalUi";

describe("conditional UI evaluation", () => {
  const rootData = {
    enabled: true,
    count: 0,
    empty: "",
    nullable: null,
    choice: "yes",
  };

  it.each([
    [
      {
        op: "equals",
        ref: { scope: "root", pointer: "/enabled" },
        value: true,
      },
      true,
    ],
    [
      { op: "equals", ref: { scope: "root", pointer: "/count" }, value: "0" },
      false,
    ],
    [{ op: "present", ref: { scope: "root", pointer: "/count" } }, true],
    [{ op: "present", ref: { scope: "root", pointer: "/empty" } }, false],
    [{ op: "present", ref: { scope: "root", pointer: "/nullable" } }, false],
    [{ op: "present", ref: { scope: "root", pointer: "/missing" } }, false],
    [
      {
        op: "in",
        ref: { scope: "root", pointer: "/choice" },
        values: ["yes", "maybe"],
      },
      true,
    ],
  ] as [ConditionalUiPredicate, boolean][])(
    "evaluates %j",
    (predicate, expected) => {
      expect(evaluateConditionalUiPredicate(predicate, { rootData })).toBe(
        expected,
      );
    },
  );

  it("supports nested boolean predicates and row ancestors", () => {
    const predicate: ConditionalUiPredicate = {
      op: "all",
      predicates: [
        {
          op: "equals",
          ref: { scope: "item", pointer: "/kind" },
          value: "detail",
        },
        {
          op: "not",
          predicate: {
            op: "equals",
            ref: { scope: "item", pointer: "/closed", ancestor: 1 },
            value: true,
          },
        },
      ],
    };
    expect(
      evaluateConditionalUiPredicate(predicate, {
        rootData,
        itemStack: [{ closed: false }, { kind: "detail" }],
      }),
    ).toBe(true);
  });

  it("uses otherwise and never mutates its contract", () => {
    const conditional = {
      when: {
        op: "equals" as const,
        ref: { scope: "root" as const, pointer: "/choice" },
        value: "no",
      },
      then: { visible: true },
      otherwise: { visible: false, interaction: "readOnly" as const },
    };
    const snapshot = JSON.parse(
      JSON.stringify(conditional),
    ) as typeof conditional;
    expect(resolveConditionalUiState(conditional, { rootData })).toEqual({
      visible: false,
      interaction: "readOnly",
    });
    expect(conditional).toEqual(snapshot);
  });

  it("removes invisible navigation nodes recursively", () => {
    const schema = filterVisibleUiSchema(
      [
        {
          type: "section",
          name: "details",
          label: "Details",
          conditional: {
            when: {
              op: "equals",
              ref: { scope: "root", pointer: "/enabled" },
              value: true,
            },
            then: { visible: false },
          },
          children: [{ type: "field", definition: "/properties/choice" }],
        },
      ],
      rootData,
    );
    expect(schema).toEqual([]);
  });
});
