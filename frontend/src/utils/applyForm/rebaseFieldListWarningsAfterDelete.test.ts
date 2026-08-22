import { rebaseFieldListWarningsAfterDelete } from "src/utils/applyForm/rebaseFieldListWarningsAfterDelete";

describe("rebaseFieldListWarningsAfterDelete", () => {
  it("rebases the innermost index and html id for a nested FieldList", () => {
    const result = rebaseFieldListWarningsAfterDelete({
      rawErrors: [
        {
          field: "$.projects[0].periods[2].amount",
          htmlField: "projects[0]--periods[2]--amount",
          message: "Amount is required",
          type: "required",
          value: null,
        },
      ],
      fieldListPath: "$.projects[0].periods",
      deletedEntryIndex: 1,
    });

    expect(result).toEqual([
      expect.objectContaining({
        field: "$.projects[0].periods[1].amount",
        htmlField: "projects[0]--periods[1]--amount",
      }),
    ]);
  });

  it("removes warnings for a deleted nested entry", () => {
    const result = rebaseFieldListWarningsAfterDelete({
      rawErrors: [
        {
          field: "$.projects[0].periods[1].amount",
          htmlField: "projects[0]--periods[1]--amount",
          message: "Amount is required",
          type: "required",
          value: null,
        },
      ],
      fieldListPath: "$.projects[0].periods",
      deletedEntryIndex: 1,
    });

    expect(result).toEqual([]);
  });
});
