import { ReadableStream as NodeReadableStream } from "stream/web";
import { RJSFSchema } from "@rjsf/utils";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApplyForm from "src/app/[locale]/(base)/workspace/applications/[applicationId]/form/[appFormId]/_components/ApplyForm";
import { UiSchema } from "src/types/applyForm/types";
import { Attachment } from "src/types/attachmentTypes";
import {
  createAdvanceStreamTrigger,
  makeAdvanceableTestStreamForTrigger,
} from "src/utils/testing/streamTestUtils";

// jsdom doesn't implement ReadableStream, which makeAdvanceableTestStreamForTrigger
// needs. Node's implementation is API compatible for the upload stream tests below.
global.ReadableStream =
  global.ReadableStream ??
  (NodeReadableStream as unknown as typeof ReadableStream);

const pushMock = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    replace: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
  }),
  useParams: () => ({ applicationId: "application-123" }),
}));

type FormActionArgs = [
  {
    applicationId: string;
    formId: string;
    formData: object;
    saved: boolean;
    error: boolean;
  },
  FormData,
];

type FormActionResult = Promise<{
  applicationId: string;
  formId: string;
  saved: boolean;
  error: boolean;
  formData: object;
}>;

const mockHandleFormAction = jest.fn<FormActionResult, FormActionArgs>();

jest.mock(
  "src/app/[locale]/(base)/workspace/applications/[applicationId]/form/[appFormId]/actions",
  () => ({
    handleFormAction: (...args: [...FormActionArgs]) =>
      mockHandleFormAction(...args),
  }),
);

const mockRevalidateTag = jest.fn<void, [string]>();
const getSessionMock = jest.fn();

jest.mock("next/cache", () => ({
  revalidateTag: (tag: string) => mockRevalidateTag(tag),
}));

jest.mock("src/services/auth/session", () => ({
  getSession: (): unknown => getSessionMock(),
}));

jest.mock("next-navigation-guard", () => ({
  useNavigationGuard: () => jest.fn(),
}));

const mockClientFetch = jest.fn();
jest.mock("src/hooks/useClientFetch", () => ({
  useClientFetch: () => ({
    clientFetch: mockClientFetch,
  }),
}));

// mock attachment FormData. The actual data is not ever processed so can
// be left empty for mocking purposes
jest.mock("src/utils/fileUtils/createFormData", () => ({
  createFormDataForFile: () => Promise.resolve(new FormData()),
}));

const formSchema: RJSFSchema = {
  title: "test schema",
  properties: {
    name: { type: "string", title: "test name", maxLength: 60 },
    dob: { type: "string", format: "date", title: "Date of birth" },
    address: { type: "string", title: "test address" },
    state: { type: "string", title: "test state" },
    checkbox: { type: "boolean", title: "I agree" },
    textarea: { type: "string", maxLength: 256, title: "Text area" },
  },
  required: ["name"],
};

const uiSchema: UiSchema = [
  {
    type: "section",
    label: "Applicant info",
    name: "ApplicantInfo",
    children: [
      {
        type: "field",
        definition: "/properties/name",
      },
      {
        type: "field",
        definition: "/properties/dob",
      },
    ],
  },
  {
    type: "section",
    label: "Applicant location",
    name: "ApplicantLocation",
    children: [
      {
        type: "field",
        definition: "/properties/address",
      },
      {
        type: "field",
        definition: "/properties/state",
      },
    ],
  },
  {
    type: "section",
    label: "Field Variations",
    name: "FieldVariations",
    children: [
      {
        type: "field",
        definition: "/properties/address",
        widget: "Select",
        schema: {
          enum: ["test select option"],
        },
      },
      {
        type: "field",
        definition: "/properties/textarea",
      },
      {
        type: "field",
        definition: "/properties/checkbox",
      },
    ],
  },
];

// mirrors the shape of the Attachment Form's schema after processing ($refs resolved, allOf merged)
const attachmentFormSchema: RJSFSchema = {
  title: "attachment form schema",
  properties: {
    att1: { type: "string", title: "Attachment 1" },
    att2: { type: "string", title: "Attachment 2" },
  },
};

const attachmentUiSchema: UiSchema = [
  {
    type: "section",
    label: "1) Attachment 1",
    name: "attachments",
    children: [
      {
        type: "field",
        definition: "/properties/att1",
        widget: "Attachment",
      },
      {
        type: "field",
        definition: "/properties/att2",
        widget: "Attachment",
      },
    ],
  },
];
const savedAttachment: Attachment = {
  application_attachment_id: "22222222-2222-4222-8222-222222222222",
  file_name: "narrative.pdf",
  download_path: "/download/narrative.pdf",
  file_size_bytes: 2048,
  mime_type: "application/pdf",
  created_at: "2024-01-01T00:00:00.000Z",
  updated_at: "2024-01-02T00:00:00.000Z",
};

const getHiddenInput = (container: HTMLElement, name: string) =>
  // eslint-disable-next-line testing-library/no-node-access
  container.querySelector<HTMLInputElement>(
    `input[type="hidden"][name="${name}"]`,
  );

describe("ApplyForm", () => {
  beforeEach(() => {
    pushMock.mockClear();
    mockHandleFormAction.mockClear();
  });

  it("renders form correctly", () => {
    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    const nameLabel = screen.getByText("test name");
    expect(nameLabel).toBeInTheDocument();
    expect(nameLabel).toHaveAttribute("for", "name");

    const nameField = screen.getByTestId("name");
    expect(nameField).toBeInTheDocument();
    expect(nameField).toBeRequired();
    expect(nameField).toHaveAttribute("type", "text");
    expect(nameField).toHaveAttribute("maxLength", "60");
    expect(nameField).toHaveAttribute("name", "name");
    expect(nameField).toHaveValue("myself");
    expect(nameField).toBeEnabled();

    const dobLabel = screen.getByText("Date of birth");
    expect(dobLabel).toBeInTheDocument();
    expect(dobLabel).toHaveAttribute("for", "dob");

    const dobField = screen.getByTestId("dob");
    expect(dobField).toBeInTheDocument();
    expect(dobField).not.toBeRequired();
    expect(dobField).toHaveAttribute("type", "date");
    expect(dobField).toBeEnabled();

    const nav = screen.getByTestId("InPageNavigation");
    expect(nav).toHaveTextContent("navTitle");

    const textareaField = screen.getByTestId("textarea");
    expect(textareaField).toBeInTheDocument();
    expect(textareaField).not.toBeRequired();
    expect(textareaField).toHaveAttribute("maxlength", "256");

    const selectField = screen.getByTestId("Select");
    expect(selectField).toBeInTheDocument();
    expect(selectField).not.toBeRequired();
    expect(screen.getAllByRole("option").length).toBe(2);
    expect(screen.getByText("test select option")).toBeInTheDocument();
    expect(selectField).toBeEnabled();

    const button = screen.getByTestId("apply-form-save");
    expect(button).toBeInTheDocument();

    expect(screen.getByTestId("apply-form-return")).toBeInTheDocument();
    expect(screen.getByText("savingAndRefreshing")).toBeInTheDocument();
    expect(screen.getByText("returnToApplication")).toBeInTheDocument();
  });

  it("recalculates typed monetary rules as a user edits the form", async () => {
    const user = userEvent.setup();
    const calculationSchema: RJSFSchema = {
      properties: {
        amount_a: { type: "string", title: "Amount A" },
        amount_b: { type: "string", title: "Amount B" },
        total: { type: "string", title: "Total" },
        server_value: { type: "string", title: "Server value" },
      },
    };
    const calculationUiSchema: UiSchema = [
      {
        type: "section",
        label: "Amounts",
        name: "amounts",
        children: [
          { type: "field", definition: "/properties/amount_a" },
          { type: "field", definition: "/properties/amount_b" },
          { type: "null", definition: "/properties/total" },
          { type: "null", definition: "/properties/server_value" },
        ],
      },
    ];

    render(
      <ApplyForm
        applicationId="application-123"
        formId="calculation-form"
        formSchema={calculationSchema}
        formRuleSchema={{
          total: {
            gg_pre_population: {
              rule: "sum_monetary",
              fields: ["amount_a", "amount_b"],
            },
          },
        }}
        savedFormData={{
          amount_a: "1.00",
          amount_b: "2.00",
          server_value: "preserve me",
        }}
        uiSchema={calculationUiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    expect(screen.getByTestId("total")).toHaveValue("3.00");
    expect(screen.getByTestId("server_value")).toHaveValue("preserve me");
    await user.clear(screen.getByTestId("amount_a"));
    await user.type(screen.getByTestId("amount_a"), "4.50");
    expect(screen.getByTestId("total")).toHaveValue("6.50");
    expect(screen.getByTestId("server_value")).toHaveValue("preserve me");
  });

  it("reconciles calculated values with the authoritative save response", async () => {
    const user = userEvent.setup();
    const consoleError = jest
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mockHandleFormAction.mockResolvedValue({
      applicationId: "application-123",
      formId: "calculation-form",
      saved: true,
      error: false,
      formData: { amount: "1.00", rate: "invalid", total: "7.01" },
    });

    render(
      <ApplyForm
        applicationId="application-123"
        formId="calculation-form"
        formSchema={{
          properties: {
            amount: { type: "string", title: "Amount" },
            rate: { type: "string", title: "Rate" },
            total: { type: "string", title: "Total" },
          },
        }}
        formRuleSchema={{
          total: {
            gg_pre_population: {
              rule: "multiply_by_percentage",
              amount: "amount",
              percentage: "rate",
            },
          },
        }}
        savedFormData={{ amount: "1.00", rate: "invalid", total: "7.00" }}
        uiSchema={[
          { type: "field", definition: "/properties/amount" },
          { type: "field", definition: "/properties/rate" },
          { type: "null", definition: "/properties/total" },
        ]}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    expect(screen.getByTestId("total")).toHaveValue("7.00");
    await user.click(screen.getByTestId("apply-form-save"));
    await waitFor(() => expect(mockHandleFormAction).toHaveBeenCalled());
    const submittedFormData = mockHandleFormAction.mock.calls.at(-1)?.[1];
    expect(submittedFormData).toBeInstanceOf(FormData);
    expect(submittedFormData?.get("total")).toBe("7.00");
    await waitFor(() => {
      expect(screen.getByTestId("total")).toHaveValue("7.01");
    });
    consoleError.mockRestore();
  });

  it("preserves current edits when a save fails after an earlier success", async () => {
    const user = userEvent.setup();
    mockHandleFormAction
      .mockResolvedValueOnce({
        applicationId: "application-123",
        formId: "simple-form",
        saved: true,
        error: false,
        formData: { name: "server value" },
      })
      .mockResolvedValueOnce({
        applicationId: "application-123",
        formId: "simple-form",
        saved: false,
        error: true,
        formData: new FormData(),
      });

    render(
      <ApplyForm
        applicationId="application-123"
        formId="simple-form"
        formSchema={{
          properties: { name: { type: "string", title: "Name" } },
        }}
        savedFormData={{ name: "original value" }}
        uiSchema={[{ type: "field", definition: "/properties/name" }]}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    await user.click(screen.getByTestId("apply-form-save"));
    await waitFor(() => {
      expect(screen.getByTestId("name")).toHaveValue("server value");
    });

    await user.clear(screen.getByTestId("name"));
    await user.type(screen.getByTestId("name"), "current edit");
    await user.click(screen.getByTestId("apply-form-save"));

    await waitFor(() => {
      expect(screen.getByTestId("name")).toHaveValue("current edit");
    });
  });

  it("recalculates repeated rows and aggregates after edits and deletion", async () => {
    const user = userEvent.setup();
    const repeatedCalculationSchema: RJSFSchema = {
      properties: {
        periods: {
          type: "array",
          items: {
            type: "object",
            properties: {
              direct: { type: "string", title: "Direct" },
              indirect: { type: "string", title: "Indirect" },
              total: { type: "string", title: "Period total" },
            },
          },
        },
        grand_total: { type: "string", title: "Grand total" },
      },
    };
    const repeatedCalculationUiSchema: UiSchema = [
      {
        type: "fieldList",
        label: "Budget periods",
        name: "periods",
        definition: "/properties/periods",
        children: [
          {
            type: "field",
            definition: "/properties/periods/items/properties/direct",
          },
          {
            type: "field",
            definition: "/properties/periods/items/properties/indirect",
          },
          {
            type: "null",
            definition: "/properties/periods/items/properties/total",
          },
        ],
      },
      {
        type: "null",
        definition: "/properties/grand_total",
      },
    ];

    render(
      <ApplyForm
        applicationId="application-123"
        formId="repeated-calculation-form"
        formSchema={repeatedCalculationSchema}
        formRuleSchema={{
          periods: {
            gg_type: "array",
            total: {
              gg_pre_population: {
                rule: "sum_monetary",
                fields: ["@THIS.direct", "@THIS.indirect"],
                order: 1,
              },
            },
          },
          grand_total: {
            gg_pre_population: {
              rule: "sum_monetary",
              fields: ["periods[*].total"],
              order: 2,
            },
          },
        }}
        savedFormData={{
          periods: [
            { direct: "10.00", indirect: "2.00" },
            { direct: "20.00", indirect: "3.00" },
          ],
        }}
        uiSchema={repeatedCalculationUiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    expect(screen.getByTestId("periods[0]--total")).toHaveValue("12.00");
    expect(screen.getByTestId("periods[1]--total")).toHaveValue("23.00");
    expect(screen.getByTestId("periods[0]--total")).toBeDisabled();
    expect(screen.getByTestId("periods[1]--total")).toBeDisabled();
    expect(screen.getByTestId("grand_total")).toHaveValue("35.00");

    await user.clear(screen.getByTestId("periods[1]--direct"));
    await user.type(screen.getByTestId("periods[1]--direct"), "30.00");
    expect(screen.getByTestId("periods[1]--total")).toHaveValue("33.00");
    expect(screen.getByTestId("grand_total")).toHaveValue("45.00");

    await user.click(
      screen.getByRole("button", { name: "deleteEntry: Budget periods 1" }),
    );
    await waitFor(() => {
      expect(screen.getByTestId("grand_total")).toHaveValue("33.00");
    });

    await user.click(
      screen.getByRole("button", { name: "addEntry: Budget periods" }),
    );
    await waitFor(() => {
      expect(screen.getByTestId("periods[1]--total")).toHaveValue("0.00");
    });
  });

  it("cannot be edited or saved when application is submitted", () => {
    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="submitted"
      />,
    );
    const button = screen.queryByTestId("apply-form-save");
    expect(button).not.toBeInTheDocument();
    const nameField = screen.getByTestId("name");
    expect(nameField).toBeDisabled();

    const dobField = screen.getByTestId("dob");
    expect(dobField).toBeDisabled();

    const selectField = screen.getByTestId("Select");
    expect(selectField).toBeDisabled();
  });
  it("displays created message when updatedAt is missing", () => {
    const timestamp = "2026-06-27T12:34:56.000Z";

    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
        createdAt={timestamp}
      />,
    );

    expect(screen.getByText(/createdMessage/i)).toBeInTheDocument();
  });

  it("displays created message when createdAt equals updatedAt exactly", () => {
    const timestamp = "2026-06-27T12:34:56.000Z";

    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
        createdAt={timestamp}
        updatedAt={timestamp}
      />,
    );

    expect(screen.getByText(/createdMessage/i)).toBeInTheDocument();
  });

  it("displays created message when createdAt and updatedAt differ by <= 1s", () => {
    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
        createdAt="2026-06-27T12:34:56.000Z"
        updatedAt="2026-06-27T12:34:56.500Z"
      />,
    );

    expect(screen.getByText(/createdMessage/i)).toBeInTheDocument();
  });

  it("displays last updated message when updatedAt differs from createdAt", () => {
    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
        createdAt="2026-06-26T12:34:56.000Z"
        updatedAt="2026-06-27T12:34:56.000Z"
      />,
    );

    expect(screen.getByText(/lastUpdatedMessage/i)).toBeInTheDocument();
  });

  it("navigates back to application when return button is clicked", () => {
    render(
      <ApplyForm
        applicationId="application-123"
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    const returnButton = screen.getByTestId("apply-form-return");
    returnButton.click();

    expect(pushMock).toHaveBeenCalledWith(
      "/workspace/applications/application-123",
    );
  });

  it("calls handleFormAction action on save", () => {
    mockHandleFormAction.mockImplementation(
      mockHandleFormAction.mockResolvedValue({
        applicationId: "test",
        formId: "test",
        saved: false,
        error: false,
        formData: new FormData(),
      }),
    );

    render(
      <ApplyForm
        applicationId="test"
        formId="test"
        formSchema={formSchema}
        savedFormData={{}}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    const button = screen.getByTestId("apply-form-save");
    button.click();

    expect(mockHandleFormAction).toHaveBeenCalledWith(
      {
        applicationId: "test",
        error: false,
        formData: new FormData(),
        formId: "test",
        saved: false,
      },

      expect.any(FormData),
    );
  });
  it("errors when form data is empty", () => {
    mockHandleFormAction.mockImplementation(
      mockHandleFormAction.mockResolvedValue({
        applicationId: "test",
        formId: "test",
        saved: false,
        error: false,
        formData: new FormData(),
      }),
    );

    render(
      <ApplyForm
        applicationId="test"
        formId="test"
        formSchema={{}}
        uiSchema={uiSchema}
        savedFormData={{}}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );
    const alert = screen.getByTestId("alert");
    expect(alert).toHaveTextContent("Error rendering form");
  });
  it("errors when form data does not conform to JSON schema", () => {
    mockHandleFormAction.mockImplementation(
      mockHandleFormAction.mockResolvedValue({
        applicationId: "test",
        formId: "test",
        saved: false,
        error: false,
        formData: new FormData(),
      }),
    );

    render(
      <ApplyForm
        applicationId="test"
        savedFormData={{}}
        formSchema={{ arbitrayField: "arbirtrary value" }}
        uiSchema={uiSchema}
        formId="test"
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    const errorMessage = screen.queryByText("Error rendering form");
    expect(errorMessage).toBeInTheDocument();
  });
  it("does not error when saved form data does not conform to form schema", () => {
    mockHandleFormAction.mockImplementation(
      mockHandleFormAction.mockResolvedValue({
        applicationId: "test",
        formId: "test",
        saved: false,
        error: false,
        formData: new FormData(),
      }),
    );

    render(
      <ApplyForm
        applicationId="test"
        savedFormData={{ arbitrayField: "arbirtrary value" }}
        formSchema={formSchema}
        uiSchema={uiSchema}
        formId="test"
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );

    // form is still correctly built
    const nameLabel = screen.getByText("test name");
    expect(nameLabel).toBeInTheDocument();
    expect(nameLabel).toHaveAttribute("for", "name");

    const errorMessage = screen.queryByText("Error rendering form");
    expect(errorMessage).not.toBeInTheDocument();
  });
  it("provides correct error message", async () => {
    mockHandleFormAction.mockResolvedValue({
      applicationId: "test",
      error: true,
      formData: new FormData(),
      formId: "test",
      saved: true,
    });

    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[
          {
            field: "$.name",
            message: "'this' is an error",
            formatted: "this is an error",
            htmlField: "name",
            value: "",
            type: "",
            definition: "/properties/name",
          },
        ]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );
    const button = screen.getByTestId("apply-form-save");
    button.click();
    // error for form
    await waitFor(() => {
      const alert = screen.getByTestId("alert");
      expect(alert).toHaveTextContent("errorTitle");
    });
    // error for field
    await waitFor(() => {
      const alert = screen.getByTestId("errorMessage");
      expect(alert).toHaveTextContent("this is an error");
    });
  });
  it("provides correct validation message", async () => {
    mockHandleFormAction.mockResolvedValue({
      applicationId: "test",
      error: false,
      formData: new FormData(),
      formId: "test",
      saved: true,
    });

    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[
          {
            field: "$.name",
            message: "'this' is an error",
            value: "",
            htmlField: "name",
            type: "",
            formatted: "this is an error",
            definition: "/properties/name",
          },
        ]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );
    const button = screen.getByTestId("apply-form-save");
    button.click();
    // error for form
    await waitFor(() => {
      const alert = screen.getByTestId("alert");
      expect(alert).toHaveTextContent("savedTitle");
    });
    await waitFor(() => {
      const alert = screen.getByTestId("alert");
      expect(alert).toHaveTextContent("validationMessage");
    });
    // error for field
    await waitFor(() => {
      const alert = screen.getByTestId("errorMessage");
      expect(alert).toHaveTextContent("this is an error");
    });
  });
  it("provides correct save message", async () => {
    mockHandleFormAction.mockResolvedValue({
      applicationId: "test",
      error: false,
      formData: new FormData(),
      formId: "test",
      saved: true,
    });

    render(
      <ApplyForm
        applicationId=""
        formId="test"
        formSchema={formSchema}
        savedFormData={{ name: "myself" }}
        uiSchema={uiSchema}
        validationWarnings={[]}
        attachments={[]}
        applicationStatus="in_progress"
      />,
    );
    const button = screen.getByTestId("apply-form-save");
    button.click();
    // error for form
    await waitFor(() => {
      const alert = screen.getByTestId("alert");
      expect(alert).toHaveTextContent("savedTitle");
    });
    await waitFor(() => {
      const alert = screen.getByTestId("alert");
      expect(alert).toHaveTextContent("savedMessage");
    });
  });

  describe("attachment widget rendering", () => {
    it("renders the virus scanning attachment widget for a saved attachment", () => {
      const { container } = render(
        <ApplyForm
          applicationId="application-123"
          formId="test"
          formSchema={attachmentFormSchema}
          savedFormData={{
            att1: savedAttachment.application_attachment_id,
          }}
          uiSchema={attachmentUiSchema}
          validationWarnings={[]}
          attachments={[savedAttachment]}
          applicationStatus="in_progress"
        />,
      );

      // the hidden input carries the saved attachment id into the form submission
      expect(getHiddenInput(container, "att1")).toHaveValue(
        savedAttachment.application_attachment_id,
      );

      // the virus scanning widget keeps its native file input mounted
      expect(screen.getAllByTestId("file-input")).toHaveLength(2);

      // the saved attachment's metadata is resolved from the attachments prop
      expect(screen.getByTestId("file-input-existing-files")).toHaveTextContent(
        "narrative.pdf",
      );
    });

    it("renders an empty virus scanning attachment field when there is no saved value", () => {
      const { container } = render(
        <ApplyForm
          applicationId="application-123"
          formId="test"
          formSchema={attachmentFormSchema}
          savedFormData={{}}
          uiSchema={attachmentUiSchema}
          validationWarnings={[]}
          attachments={[savedAttachment]}
          applicationStatus="in_progress"
        />,
      );

      expect(screen.getByText("Attachment 1")).toBeInTheDocument();
      expect(screen.getByText("Attachment 2")).toBeInTheDocument();
      expect(getHiddenInput(container, "att1")).toHaveValue("");
      expect(getHiddenInput(container, "att2")).toHaveValue("");
      expect(screen.getAllByTestId("file-input")).toHaveLength(2);
      expect(
        screen.queryByTestId("file-input-existing-files"),
      ).not.toBeInTheDocument();
    });
  });

  describe("save button during attachment uploads", () => {
    const renderAttachmentForm = () =>
      render(
        <ApplyForm
          applicationId="application-123"
          formId="test"
          formSchema={attachmentFormSchema}
          savedFormData={{}}
          uiSchema={attachmentUiSchema}
          validationWarnings={[]}
          attachments={[]}
          applicationStatus="in_progress"
        />,
      );

    const getSaveButton = () => screen.getByTestId("apply-form-save");

    const uploadFileTo = async (fileInput: HTMLElement, fileName: string) => {
      await userEvent.upload(
        fileInput,
        new File(["file content"], fileName, { type: "application/pdf" }),
      );
    };

    it("keeps the save button enabled without a tooltip when no uploads are in progress", () => {
      renderAttachmentForm();
      const saveButton = getSaveButton();
      expect(saveButton).toBeEnabled();
      expect(saveButton).toHaveAttribute("aria-disabled", "false");
      expect(screen.queryByTestId("triggerElement")).not.toBeInTheDocument();
      expect(screen.queryByTestId("tooltipBody")).not.toBeInTheDocument();
    });

    it("disables the save button while an attachment upload is in progress", async () => {
      // the upload request never resolves, so the upload stays in progress
      mockClientFetch.mockReturnValue(new Promise(() => {}));
      renderAttachmentForm();

      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      });
      expect(getSaveButton()).toHaveAccessibleDescription(
        "saveDisabledTooltipMessage",
      );
    });

    it("keeps the save button rendered while transitioning to disabled", async () => {
      mockClientFetch.mockReturnValue(new Promise(() => {}));
      renderAttachmentForm();
      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");
      expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      expect(screen.getByTestId("triggerElement")).toBeInTheDocument();
    });

    it("blocks form submission when the save button is clicked during an upload", async () => {
      mockClientFetch.mockReturnValue(new Promise(() => {}));
      renderAttachmentForm();

      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      });

      await userEvent.click(getSaveButton());
      expect(mockHandleFormAction).not.toHaveBeenCalled();
    });

    it("re-enables the save button after an upload fails", async () => {
      let failUpload: (error: Error) => void = () => undefined;
      mockClientFetch.mockReturnValue(
        new Promise((_resolve, reject) => {
          failUpload = reject;
        }),
      );
      renderAttachmentForm();
      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      });

      failUpload(new Error("upload failed"));

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "false");
      });
      expect(screen.queryByTestId("triggerElement")).not.toBeInTheDocument();
    });

    it("re-enables the save button after an upload completes successfully", async () => {
      const trigger = createAdvanceStreamTrigger();
      const scanStream = makeAdvanceableTestStreamForTrigger(
        [
          JSON.stringify({
            status: "scan-complete",
            pendingFileId: "pending-file-1",
          }),
        ],
        trigger,
      );
      mockClientFetch.mockImplementation(
        (url: string) =>
          url === "/api/file"
            ? Promise.resolve({ body: scanStream }) // keeps stream in progress
            : Promise.resolve({ data: savedAttachment }), // triggers onComplete and decrements uploading counter
      );

      renderAttachmentForm();

      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      });

      trigger.advance();

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "false");
      });
      expect(screen.queryByTestId("triggerElement")).not.toBeInTheDocument();
    });

    it("re-enables the save button when the scan stream errors", async () => {
      const trigger = createAdvanceStreamTrigger();
      // passing ["error"] invokes error
      const scanStream = makeAdvanceableTestStreamForTrigger(
        ["error"],
        trigger,
      );
      mockClientFetch.mockResolvedValue({ body: scanStream });

      renderAttachmentForm();

      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "true");
      });

      trigger.advance();

      await waitFor(() => {
        expect(getSaveButton()).toHaveAttribute("aria-disabled", "false");
      });
    });

    it("shows a tooltip only while the disabled save button is hovered", async () => {
      mockClientFetch.mockReturnValue(new Promise(() => {}));
      renderAttachmentForm();

      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");

      const tooltipTrigger = await screen.findByTestId("triggerElement");
      expect(
        within(tooltipTrigger).getByTestId("apply-form-save"),
      ).toHaveAttribute("aria-disabled", "true");

      // the tooltip is hidden until the trigger is hovered over
      expect(screen.getByTestId("tooltipBody")).toHaveAttribute(
        "aria-hidden",
        "true",
      );

      await userEvent.hover(tooltipTrigger);
      expect(screen.getByTestId("tooltipBody")).toHaveTextContent(
        "saveDisabledTooltip",
      );
      expect(screen.getByTestId("tooltipBody")).toHaveAttribute(
        "aria-hidden",
        "false",
      );
      await userEvent.unhover(tooltipTrigger);
      expect(screen.getByTestId("tooltipBody")).toHaveAttribute(
        "aria-hidden",
        "true",
      );
    });

    it("shows the tooltip when the disabled save button receives keyboard focus", async () => {
      mockClientFetch.mockReturnValue(new Promise(() => {}));
      renderAttachmentForm();
      const [firstFileInput] = await screen.findAllByTestId("file-input-input");
      await uploadFileTo(firstFileInput, "attachment.pdf");
      await screen.findByTestId("triggerElement");

      act(() => {
        getSaveButton().focus();
      });
      expect(screen.getByTestId("tooltipBody")).toHaveAttribute(
        "aria-hidden",
        "false",
      );

      act(() => {
        getSaveButton().blur(); // lose focus on button
      });
      expect(screen.getByTestId("tooltipBody")).toHaveAttribute(
        "aria-hidden",
        "true",
      );
    });
  });
});
