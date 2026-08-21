import { RJSFSchema } from "@rjsf/utils";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { UswdsWidgetProps } from "src/types/applyForm/types";

import EncodedCheckboxGroupWidget from "src/components/apply-form/widgets/EncodedCheckboxGroupWidget";

const schema: RJSFSchema = {
  type: "string",
  title: "Revision type",
  enum: ["A", "B", "C", "D", "E", "AC", "AD", "BC", "BD"],
  "x-encoded-checkbox-group": {
    choices: [
      { code: "A", label: "A. Increase Award" },
      { code: "B", label: "B. Decrease Award" },
      { code: "C", label: "C. Increase Duration" },
      { code: "D", label: "D. Decrease Duration" },
      { code: "E", label: "E. Other" },
    ],
    combinations: ["A", "B", "C", "D", "E", "AC", "AD", "BC", "BD"].map(
      (value) => ({ value, members: [...value] }),
    ),
  },
};

const props = {
  id: "application_type--revision_code",
  schema,
  value: "A",
  required: true,
  disabled: false,
  readOnly: false,
  rawErrors: [],
  options: {},
  onChange: jest.fn(),
  onBlur: jest.fn(),
  onFocus: jest.fn(),
} as unknown as UswdsWidgetProps;

describe("EncodedCheckboxGroupWidget", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders the decoded selection and submits only the encoded wire value", () => {
    render(
      <form data-testid="revision-form">
        <EncodedCheckboxGroupWidget {...props} />
      </form>,
    );

    expect(
      screen.getByRole("checkbox", { name: "A. Increase Award" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "C. Increase Duration" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("checkbox", { name: "B. Decrease Award" }),
    ).toBeDisabled();
    expect(screen.getByDisplayValue("A")).toHaveValue("A");
    expect(screen.getByDisplayValue("A")).toHaveAttribute(
      "name",
      "application_type--revision_code",
    );
    expect([
      ...new FormData(
        screen.getByTestId<HTMLFormElement>("revision-form"),
      ).entries(),
    ]).toEqual([["application_type--revision_code", "A"]]);
  });

  it("encodes only source-approved combinations", async () => {
    const user = userEvent.setup();
    render(
      <form data-testid="revision-form">
        <EncodedCheckboxGroupWidget {...props} />
      </form>,
    );

    await user.click(
      screen.getByRole("checkbox", { name: "C. Increase Duration" }),
    );
    expect(props.onChange).toHaveBeenCalledWith("AC");
    expect([
      ...new FormData(
        screen.getByTestId<HTMLFormElement>("revision-form"),
      ).entries(),
    ]).toEqual([["application_type--revision_code", "AC"]]);
  });

  it("keeps Other exclusive", () => {
    render(<EncodedCheckboxGroupWidget {...props} value="E" />);

    expect(screen.getByRole("checkbox", { name: "E. Other" })).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "A. Increase Award" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("checkbox", { name: "D. Decrease Duration" }),
    ).toBeDisabled();
  });

  it("reconciles an authoritative external value", () => {
    const { rerender } = render(
      <EncodedCheckboxGroupWidget {...props} value="AC" />,
    );
    expect(
      screen.getByRole("checkbox", { name: "C. Increase Duration" }),
    ).toBeChecked();

    rerender(<EncodedCheckboxGroupWidget {...props} value="E" />);

    expect(screen.getByRole("checkbox", { name: "E. Other" })).toBeChecked();
    expect(screen.getByDisplayValue("E")).toBeInTheDocument();
  });

  it("fails closed when the encoded contract does not match the schema enum", () => {
    expect(() =>
      render(
        <EncodedCheckboxGroupWidget
          {...props}
          schema={{
            ...schema,
            enum: [...(schema.enum ?? []), "AB"],
          }}
        />,
      ),
    ).toThrow("combinations must exactly match schema enum values");
  });
});
