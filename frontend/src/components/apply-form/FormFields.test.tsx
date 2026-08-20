import { RJSFSchema } from "@rjsf/utils";
import { render, screen } from "@testing-library/react";
import { UiSchema } from "src/types/applyForm/types";
import { addPrintWidgetToFields } from "src/utils/applyForm/applyFormUtils";

import { FormFields } from "src/components/apply-form/FormFields";

const mockMergeAllOf = jest.fn();

jest.mock("json-schema-merge-allof", () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockMergeAllOf(...args) as unknown,
}));

describe("buildFormTreeRecursive", () => {
  it("reacts to typed visibility and preserves hidden field values in the DOM", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        showDetails: { type: "boolean", title: "Show details" },
        details: { type: "string", title: "Details" },
      },
    };
    const conditionalUiSchema: UiSchema = [
      { type: "field", definition: "/properties/showDetails" },
      {
        type: "field",
        definition: "/properties/details",
        conditional: {
          when: {
            op: "equals",
            ref: { scope: "root", pointer: "/showDetails" },
            value: true,
          },
          then: { visible: true },
          otherwise: { visible: false },
        },
      },
    ];

    const { rerender } = render(
      <FormFields
        errors={null}
        formData={{ showDetails: false, details: "preserved" }}
        schema={schema}
        uiSchema={conditionalUiSchema}
      />,
    );
    const details = screen.getByTestId("details");
    expect(details).toHaveValue("preserved");
    expect(details).not.toBeVisible();

    rerender(
      <FormFields
        errors={null}
        formData={{ showDetails: true, details: "preserved" }}
        schema={schema}
        uiSchema={conditionalUiSchema}
      />,
    );
    expect(screen.getByTestId("details")).toBeVisible();
  });

  it("applies conditional requiredness and interaction without overriding a lock", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: { detail: { type: "string", title: "Detail" } },
    };
    const conditionalUiSchema: UiSchema = [
      {
        type: "field",
        definition: "/properties/detail",
        conditional: {
          when: {
            op: "present",
            ref: { scope: "root", pointer: "/detail" },
          },
          then: { interaction: "readOnly" },
        },
      },
    ];
    render(
      <FormFields
        errors={null}
        formData={{ detail: "fixed" }}
        schema={schema}
        uiSchema={conditionalUiSchema}
        formContext={{
          rootSchema: schema,
          rootFormData: { detail: "fixed" },
          activeConditionalRequiredPaths: ["$.detail"],
        }}
        isFormLocked
      />,
    );
    const detail = screen.getByTestId("detail");
    expect(detail).toBeRequired();
    expect(detail).toBeDisabled();
  });

  it("normalizes readOnly to disabled for controls without native readonly semantics", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: { accepted: { type: "boolean", title: "Accepted" } },
    };
    render(
      <FormFields
        errors={null}
        formData={{ accepted: true }}
        schema={schema}
        uiSchema={[
          {
            type: "field",
            definition: "/properties/accepted",
            conditional: {
              when: {
                op: "equals",
                ref: { scope: "root", pointer: "/accepted" },
                value: true,
              },
              then: { interaction: "readOnly" },
            },
          },
        ]}
      />,
    );
    expect(screen.getByRole("checkbox", { name: "Accepted" })).toBeDisabled();
  });

  it("prints the SF-424 Short certification description without printing unrelated descriptions", () => {
    const certificationDescription =
      "** The list of certifications and assurances, or an internet site where you may obtain this list, is contained in the announcement or agency specific instructions. By signing this application, I certify (1) to the statements contained in the list of certifications and (2) that the statements herein are true, complete and accurate to the best of my knowledge. I also provide the required assurances and agree to comply with any resulting terms if I accept an award. I am aware that any false, fictitious, or fraudulent statements or claims may subject me to criminal, civil, or administrative penalties. (U.S. Code, Title 18, Section 1001)";
    const unrelatedDescription = "Editable-form guidance only.";
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        application_certification: {
          type: "boolean",
          title: "** I Agree",
          description: certificationDescription,
        },
        authorized_representative_title: {
          type: "string",
          title: "Title",
          description: unrelatedDescription,
        },
      },
    };
    const uiSchema: UiSchema = [
      {
        type: "section",
        name: "authorized_representative",
        label: "9. Authorized Representative",
        children: [
          {
            type: "field",
            definition: "/properties/application_certification",
            printDescription: true,
          },
          {
            type: "field",
            definition: "/properties/authorized_representative_title",
          },
        ],
      },
    ];

    render(
      <FormFields
        errors={null}
        formData={{
          application_certification: true,
          authorized_representative_title: "Director",
        }}
        schema={schema}
        uiSchema={addPrintWidgetToFields(uiSchema)}
      />,
    );

    const agreementTitle = screen.getByText("** I Agree");
    const description = screen.getByText(certificationDescription);
    const savedValue = screen.getByText("Yes");

    expect(screen.getAllByText(certificationDescription)).toHaveLength(1);
    expect(description).toHaveTextContent(
      /^\*\* The list of certifications.*By signing this application/,
    );
    expect(screen.queryByText(unrelatedDescription)).not.toBeInTheDocument();
    expect(
      agreementTitle.compareDocumentPosition(description) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      description.compareDocumentPosition(savedValue) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("should build a tree for a simple schema", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        name: { type: "string", title: "Name" },
        age: { type: "number", title: "Age" },
      },
    };

    const uiSchema: UiSchema = [
      { type: "field", definition: "/properties/name" },
      { type: "field", definition: "/properties/age" },
    ];

    const errors = null;
    const formData = { name: "John", age: 30 };

    render(
      <FormFields
        errors={errors}
        formData={formData}
        schema={schema}
        uiSchema={uiSchema}
      />,
    );

    // assert field inputs
    const nameField = screen.getByTestId("name");
    expect(nameField).toBeInTheDocument();
    expect(nameField).toHaveValue("John");

    const ageField = screen.getByTestId("age");
    expect(ageField).toBeInTheDocument();
    expect(ageField).toHaveValue(30);
  });

  it("should build a tree for a nested schema", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        address: {
          type: "object",
          properties: {
            street: { type: "string", title: "Street" },
            city: { type: "string", title: "City" },
          },
        },
      },
    };

    const uiSchema: UiSchema = [
      {
        name: "address",
        type: "section",
        label: "Address",
        children: [
          {
            type: "field",
            definition: "/properties/address/properties/street",
          },
          { type: "field", definition: "/properties/address/properties/city" },
        ],
      },
    ];

    const errors = null;
    const formData = { address: { street: "123 Main St", city: "Metropolis" } };

    render(
      <FormFields
        errors={errors}
        formData={formData}
        schema={schema}
        uiSchema={uiSchema}
      />,
    );

    const fieldSets = screen.getAllByTestId("fieldset");
    expect(fieldSets).toHaveLength(1);
    expect(fieldSets[0]).toHaveAttribute("id", "form-section-address");

    const inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(2);

    expect(screen.getByTestId("address--street")).toBeInTheDocument();
    expect(screen.getByTestId("address--city")).toBeInTheDocument();
  });

  it("should handle empty uiSchema gracefully", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        name: { type: "string", title: "Name" },
      },
    };

    const uiSchema: UiSchema = [];
    const errors = null;
    const formData = { name: "John" };

    render(
      <FormFields
        errors={errors}
        formData={formData}
        schema={schema}
        uiSchema={uiSchema}
      />,
    );

    const fieldSets = screen.queryAllByTestId("fieldset");
    expect(fieldSets).toHaveLength(0);
  });

  it("should handle nested children in uiSchema", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        section: {
          type: "object",
          properties: {
            field1: { type: "string", title: "Field 1" },
            field2: { type: "string", title: "Field 2" },
          },
        },
      },
    };

    const uiSchema: UiSchema = [
      {
        name: "section",
        type: "section",
        label: "Section",
        children: [
          {
            type: "field",
            definition: "/properties/section/properties/field1",
          },
          {
            type: "field",
            definition: "/properties/section/properties/field2",
          },
        ],
      },
    ];

    const errors = null;
    const formData = { section: { field1: "Value 1", field2: "Value 2" } };

    render(
      <FormFields
        errors={errors}
        formData={formData}
        schema={schema}
        uiSchema={uiSchema}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Section" }),
    ).toBeInTheDocument();

    const inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(2);

    expect(screen.getByTestId("section--field1")).toBeInTheDocument();
    expect(screen.getByTestId("section--field2")).toBeInTheDocument();
  });

  it("should render a Table multiField widget inside a section", () => {
    const schema: RJSFSchema = {
      type: "object",
      properties: {
        first_value: {
          type: "number",
          title: "First Value",
        },
        second_value: {
          type: "number",
          title: "Second Value",
          readOnly: true,
        },
      },
    };

    const uiSchema: UiSchema = [
      {
        type: "section",
        name: "table_demo",
        label: "Table Demo",
        children: [
          {
            type: "multiField",
            name: "summary_table_test",
            widget: "Table",
            definition: ["/properties/first_value", "/properties/second_value"],
            children: {
              columns: [
                {
                  columnHeader: "Item",
                  width: 40,
                },
                {
                  columnHeader: "First Value",
                  width: 30,
                },
                {
                  columnHeader: "Second Value",
                  width: 30,
                },
              ],
              rows: [
                {
                  cells: [
                    {
                      type: "plainText",
                      staticContent: "Item 1",
                    },
                    {
                      type: "input",
                      definition: "/properties/first_value",
                    },
                    {
                      type: "readOnly",
                      definition: "/properties/second_value",
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    ];

    render(
      <FormFields
        errors={null}
        formData={{
          first_value: 2500,
          second_value: 1000,
        }}
        schema={schema}
        uiSchema={uiSchema}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Table Demo" }),
    ).toBeInTheDocument();

    const table = screen.getByTestId("table");

    expect(table).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(3);
    expect(screen.getAllByRole("row")).toHaveLength(2);
    expect(screen.getAllByRole("cell")).toHaveLength(3);

    expect(
      screen.getByRole("columnheader", { name: "Item" }),
    ).toBeInTheDocument();
  });

  describe("FormFields formContext forwarding", () => {
    it("forwards formContext to rendered widgets", () => {
      const schema: RJSFSchema = {
        type: "object",
        properties: {
          example: { type: "string", title: "Example" },
        },
      };

      const uiSchema: UiSchema = [
        {
          type: "field",
          definition: "/properties/example",
        },
      ];

      const formContext = {
        rootFormData: { activity_line_items: [{ activity_title: "Test" }] },
        rootSchema: schema,
      };

      render(
        <FormFields
          errors={null}
          formData={{ example: "hello" }}
          schema={schema}
          uiSchema={uiSchema}
          formContext={formContext}
        />,
      );

      // grab the rendered input
      const input = screen.getByTestId("example");

      expect(input).toBeInTheDocument();

      // verify that rendering still works with formContext
      expect(input).toHaveValue("hello");
    });
  });
});
