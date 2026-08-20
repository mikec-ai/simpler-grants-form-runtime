import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FieldListGroupItem } from "src/types/applyForm/types";

import FieldListWidget from "src/components/apply-form/widgets/FieldListWidget";

jest.mock("src/components/apply-form/widgets/WidgetRenderers", () => ({
  renderWidget: jest.fn(
    ({
      props,
    }: {
      props: {
        id: string;
        value?: unknown;
        rawErrors?: string[];
        additionalDescribedById?: string;
        onChange?: (value: unknown) => void;
      };
    }) => {
      const displayValue =
        typeof props.value === "string" ||
        typeof props.value === "number" ||
        typeof props.value === "boolean"
          ? String(props.value)
          : "";

      return (
        <div>
          <input
            data-testid="mock-widget"
            data-widget-id={props.id}
            data-entry-description-id={props.additionalDescribedById}
            aria-label={props.id}
            value={displayValue}
            onChange={(event) => props.onChange?.(event.target.value)}
          />
          {props.rawErrors?.map((error) => (
            <p key={error}>{error}</p>
          ))}
        </div>
      );
    },
  ),
}));

const baseGroupDefinition = [
  {
    widget: "Text" as const,
    baseId: "contacts[~~index~~]--first_name",
    definition: "/properties/contact_people_test/items/properties/first_name",
    storagePath: ["first_name"],
    generalProps: {
      schema: { type: "string", title: "First Name" },
      rawErrors: [],
      options: {},
    },
  },
];

const nestedGroupDefinition = [
  {
    widget: "Text" as const,
    baseId: "contacts[~~index~~]--address--street1",
    definition:
      "/properties/contact_people_test/items/properties/address/properties/street1",
    storagePath: ["address", "street1"],
    generalProps: {
      schema: { type: "string", title: "Street 1" },
      rawErrors: [],
      options: {},
    },
  },
];

const repeatingNestedGroupDefinition = [
  {
    widget: "FieldList",
    baseId: "projects[~~index~~]--periods",
    definition: "/properties/projects/items/properties/periods",
    storagePath: ["periods"],
    fieldListProps: {
      schema: { type: "array", title: "Budget periods" },
      label: "Budget periods",
      name: "periods",
      minItems: 1,
      groupDefinition: [
        {
          widget: "Text",
          baseId: "periods[~~index~~]--amount",
          definition:
            "/properties/projects/items/properties/periods/items/properties/amount",
          storagePath: ["amount"],
          generalProps: {
            schema: { type: "number", title: "Amount" },
            rawErrors: [],
            options: {},
          },
        },
      ],
    },
  },
] satisfies FieldListGroupItem[];

const deeplyNestedGroupDefinition = [
  {
    ...repeatingNestedGroupDefinition[0],
    fieldListProps: {
      ...repeatingNestedGroupDefinition[0].fieldListProps,
      groupDefinition: [
        {
          widget: "FieldList",
          baseId: "periods[~~index~~]--line_items",
          definition:
            "/properties/projects/items/properties/periods/items/properties/line_items",
          storagePath: ["line_items"],
          fieldListProps: {
            schema: { type: "array", title: "Line items" },
            label: "Line items",
            name: "line_items",
            minItems: 1,
            groupDefinition: [
              {
                widget: "Text",
                baseId: "line_items[~~index~~]--name",
                definition:
                  "/properties/projects/items/properties/periods/items/properties/line_items/items/properties/name",
                storagePath: ["name"],
                generalProps: {
                  schema: { type: "string", title: "Name" },
                  rawErrors: [],
                  options: {},
                },
              },
            ],
          },
        },
      ],
    },
  },
] satisfies FieldListGroupItem[];

describe("FieldListWidget", () => {
  it("renders label, description, and minimum entry widgets", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        description="Add contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Contacts" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Add contacts")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /contacts\s+1/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("mock-widget")).toHaveLength(1);
  });

  it("renders no entries when minItems is 0", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={0}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(
      screen.queryByRole("heading", { name: /contacts\s+1/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("mock-widget")).toHaveLength(0);
  });

  it("renders no entries when minItems is undefined", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(
      screen.queryByRole("heading", { name: /contacts\s+1/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryAllByTestId("mock-widget")).toHaveLength(0);
  });

  it("renders minItems number of entries", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={2}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(
      screen.getByRole("heading", { name: /contacts\s+1/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /contacts\s+2/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("mock-widget")).toHaveLength(2);
  });

  it("renders nested repeating groups with unique indexed input ids", () => {
    render(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={repeatingNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={["projects/periods/amount"]}
        name="projects"
        value={[{ periods: [{ amount: 100 }] }, { periods: [{ amount: 200 }] }]}
      />,
    );

    expect(
      screen.getAllByRole("heading", { name: "Budget periods", level: 5 }),
    ).toHaveLength(2);
    expect(
      screen.getAllByRole("heading", { name: "Budget periods 1", level: 6 }),
    ).toHaveLength(2);
    expect(
      screen.getByRole("button", {
        name: "addEntry: Budget periods — Projects 1",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "addEntry: Budget periods — Projects 2",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("mock-widget")).toHaveLength(2);
    expect(
      screen.getByLabelText("projects[0]--periods[0]--amount"),
    ).toHaveValue("100");
    expect(
      screen.getByLabelText("projects[1]--periods[0]--amount"),
    ).toHaveValue("200");
  });

  it("preserves local edits across equivalent props and accepts authoritative changes", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={repeatingNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="projects"
        value={[{ periods: [{ amount: 100 }] }]}
      />,
    );

    const amount = screen.getByLabelText("projects[0]--periods[0]--amount");
    await user.clear(amount);
    await user.type(amount, "250");

    rerender(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={repeatingNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="projects"
        value={[{ periods: [{ amount: 100 }] }]}
      />,
    );

    expect(
      screen.getByLabelText("projects[0]--periods[0]--amount"),
    ).toHaveValue("250");

    rerender(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={repeatingNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="projects"
        value={[{ periods: [{ amount: 500 }] }]}
      />,
    );

    expect(
      screen.getByLabelText("projects[0]--periods[0]--amount"),
    ).toHaveValue("500");
  });

  it("propagates nested entry additions through the outer FieldList value", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={repeatingNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={["projects/periods/amount"]}
        name="projects"
        value={[{ periods: [{ amount: 100 }] }]}
        onChange={onChange}
      />,
    );

    const nestedList = screen.getByRole("group", { name: "Budget periods" });
    await user.click(
      within(nestedList).getByRole("button", {
        name: "addEntry: Budget periods — Projects 1",
      }),
    );

    expect(onChange).toHaveBeenLastCalledWith([
      { periods: [{ amount: 100 }, {}] },
    ]);
    expect(within(nestedList).getAllByTestId("mock-widget")).toHaveLength(2);
  });

  it("keeps sibling nested lists with the same terminal name independent", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    const consoleError = jest
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    const siblingPeriods = ["direct_costs", "indirect_costs"].map(
      (costType) => ({
        widget: "FieldList" as const,
        baseId: `projects[~~index~~]--${costType}--periods`,
        definition: `/properties/projects/items/properties/${costType}/properties/periods`,
        storagePath: [costType, "periods"],
        fieldListProps: {
          schema: { type: "array", title: `${costType} periods` },
          label:
            costType === "direct_costs"
              ? "Direct budget periods"
              : "Indirect budget periods",
          name: "periods",
          minItems: 1,
          groupDefinition: [
            {
              widget: "Text" as const,
              baseId: `${costType}--periods[~~index~~]--amount`,
              definition: `/properties/projects/items/properties/${costType}/properties/periods/items/properties/amount`,
              storagePath: ["amount"],
              generalProps: {
                schema: { type: "number", title: "Amount" },
                rawErrors: [],
                options: {},
              },
            },
          ],
        },
      }),
    ) satisfies FieldListGroupItem[];

    try {
      render(
        <FieldListWidget
          id="projects"
          key="projects"
          schema={{ type: "array", title: "Projects" }}
          label="Projects"
          groupDefinition={siblingPeriods}
          rawErrors={[]}
          requiredFields={[]}
          name="projects"
          value={[
            {
              direct_costs: { periods: [{ amount: 100 }] },
              indirect_costs: { periods: [{ amount: 200 }] },
            },
          ]}
          onChange={onChange}
        />,
      );

      const directList = screen.getByRole("group", {
        name: "Direct budget periods",
      });
      const indirectList = screen.getByRole("group", {
        name: "Indirect budget periods",
      });

      await user.click(
        within(directList).getByRole("button", { name: /addEntry/i }),
      );

      expect(within(directList).getAllByTestId("mock-widget")).toHaveLength(2);
      expect(within(indirectList).getAllByTestId("mock-widget")).toHaveLength(
        1,
      );
      expect(onChange).toHaveBeenLastCalledWith([
        {
          direct_costs: { periods: [{ amount: 100 }, {}] },
          indirect_costs: { periods: [{ amount: 200 }] },
        },
      ]);
      expect(
        consoleError.mock.calls.some(([message]) =>
          String(message).includes("same key"),
        ),
      ).toBe(false);
    } finally {
      consoleError.mockRestore();
    }
  });

  it("preserves semantic heading levels beyond native h6", () => {
    render(
      <FieldListWidget
        id="projects"
        key="projects"
        schema={{ type: "array", title: "Projects" }}
        label="Projects"
        groupDefinition={deeplyNestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="projects"
        value={[{ periods: [{ line_items: [{ name: "Personnel" }] }] }]}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Line items", level: 7 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Line items 1", level: 8 }),
    ).toBeInTheDocument();
  });

  it("adds a row", async () => {
    const user = userEvent.setup();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    await user.click(screen.getByRole("button", { name: /addEntry/i }));

    expect(
      screen.getByRole("heading", { name: /contacts\s+2/i }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("mock-widget")).toHaveLength(2);
  });

  it("preserves row identity when deleting and then adding", async () => {
    const user = userEvent.setup();
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
        value={[{ first_name: "A" }, { first_name: "B" }]}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "deleteEntry: Contacts 1" }),
    );
    await user.click(
      screen.getByRole("button", { name: "addEntry: Contacts" }),
    );

    const inputs = screen.getAllByTestId("mock-widget");
    expect(inputs).toHaveLength(2);
    expect(inputs[0]).toHaveValue("B");
    expect(inputs[1]).toHaveValue("");
  });

  it("disables add when maxItems is reached", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        maxItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(screen.getByRole("button", { name: /addEntry/i })).toBeDisabled();
  });

  it("removes a row without going below minItems", async () => {
    const user = userEvent.setup();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        value={[{}, {}]}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    const deleteButtons = screen.getAllByRole("button", {
      name: /deleteEntry/i,
    });

    await user.click(deleteButtons[0]);

    expect(
      screen.queryByRole("heading", { name: /contacts\s+2/i }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByTestId("mock-widget")).toHaveLength(1);
  });

  it("disables delete when minItems is reached", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(
      screen.getByRole("button", { name: /deleteEntry: Contacts 1/i }),
    ).toBeDisabled();
  });

  it("renders FieldList child errors inline", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[
          {
            type: "required",
            field: "$.contacts[0].first_name",
            message: "first_name is required",
            value: null,
            formatted: "First Name is required",
            definition:
              "/properties/contact_people_test/items/properties/first_name",
            htmlField: "contacts[0]--first_name",
          },
        ]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(screen.getByText("First Name is required")).toBeInTheDocument();
  });

  it("passes the FieldList entry heading id to child widgets", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    const entryHeading = screen.getByRole("heading", {
      name: /contacts\s+1/i,
    });

    expect(screen.getByTestId("mock-widget")).toHaveAttribute(
      "data-entry-description-id",
      entryHeading.id,
    );
  });

  it("renders nested FieldList values from storagePath", () => {
    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        value={[{ address: { street1: "123 Main" } }]}
        groupDefinition={nestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    expect(screen.getByLabelText("contacts[0]--address--street1")).toHaveValue(
      "123 Main",
    );
  });

  it("updates nested FieldList values using storagePath", async () => {
    const user = userEvent.setup();
    const onChangeMock = jest.fn();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        value={[{}]}
        groupDefinition={nestedGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
        onChange={onChangeMock}
      />,
    );

    await user.type(
      screen.getByLabelText("contacts[0]--address--street1"),
      "123 Main",
    );

    expect(onChangeMock).toHaveBeenLastCalledWith([
      { address: { street1: "123 Main" } },
    ]);
  });

  it("marks the form dirty when a FieldList child field changes", async () => {
    const user = userEvent.setup();
    const markFormDirtyMock = jest.fn();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
        formContext={{
          widgetSupport: {
            markFormDirty: markFormDirtyMock,
          },
        }}
      />,
    );

    await user.type(screen.getByLabelText("contacts[0]--first_name"), "Jane");

    expect(markFormDirtyMock).toHaveBeenCalled();
  });

  it("marks the form dirty when a FieldList row is added", async () => {
    const user = userEvent.setup();
    const markFormDirtyMock = jest.fn();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
        formContext={{
          widgetSupport: {
            markFormDirty: markFormDirtyMock,
          },
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /addEntry/i }));

    expect(markFormDirtyMock).toHaveBeenCalledTimes(1);
  });

  it("preserves unsaved entry values when deleting another entry", async () => {
    const user = userEvent.setup();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={2}
        maxItems={3}
        value={[{ first_name: "One" }, { first_name: "Two" }]}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
      />,
    );

    await user.click(screen.getByRole("button", { name: /addEntry/i }));
    await user.type(screen.getByLabelText("contacts[2]--first_name"), "Three");

    const deleteButtons = screen.getAllByRole("button", {
      name: /deleteEntry/i,
    });

    await user.click(deleteButtons[1]);

    expect(screen.getByLabelText("contacts[1]--first_name")).toHaveValue(
      "Three",
    );
  });

  it("marks the form dirty when a FieldList row is deleted", async () => {
    const user = userEvent.setup();
    const markFormDirtyMock = jest.fn();

    render(
      <FieldListWidget
        id="contacts"
        key="contacts"
        schema={{ type: "array", title: "Contacts" }}
        label="Contacts"
        minItems={1}
        value={[{}, {}]}
        groupDefinition={baseGroupDefinition}
        rawErrors={[]}
        requiredFields={[]}
        name="contacts"
        formContext={{
          widgetSupport: {
            markFormDirty: markFormDirtyMock,
          },
        }}
      />,
    );

    const deleteButtons = screen.getAllByRole("button", {
      name: /deleteEntry/i,
    });

    await user.click(deleteButtons[0]);

    expect(markFormDirtyMock).toHaveBeenCalledTimes(1);
  });
});
