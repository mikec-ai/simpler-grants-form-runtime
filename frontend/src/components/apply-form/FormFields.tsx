import { RJSFSchema } from "@rjsf/utils";
import type { ResolvedConditionalUiState } from "src/types/applyForm/conditionalUiTypes";
import {
  FormattedFormValidationWarning,
  GeneralRecord,
  UiSchema,
  UiSchemaField,
  UiSchemaFieldList,
  UiSchemaNode,
} from "src/types/applyForm/types";
import {
  getRequiredProperties,
  isFieldRequired,
  jsonSchemaPointerToPath,
} from "src/utils/applyForm/applyFormUtils";
import {
  resolveConditionalUiState,
  supportsNativeReadOnly,
} from "src/utils/applyForm/evaluateConditionalUi";
import { getFieldConfig } from "src/utils/applyForm/getFieldConfig";

import React, { JSX } from "react";
import { Alert } from "@trussworks/react-uswds";

import { renderWidget, wrapSection } from "./widgets/WidgetRenderers";

type RootBudgetFormContext = {
  rootSchema: RJSFSchema;
  rootFormData: unknown;
  itemStack?: GeneralRecord[];
  activeConditionalRequiredPaths?: string[];
};

const isRenderableFieldNode = (
  node: UiSchemaNode,
): node is UiSchemaField | UiSchemaFieldList =>
  node.type === "fieldList" ||
  node.type === "multiField" ||
  "definition" in node ||
  "schema" in node;

const combineConditionalState = (
  parent: ResolvedConditionalUiState,
  child: ResolvedConditionalUiState,
): ResolvedConditionalUiState => {
  const interaction =
    parent.interaction === "disabled" || child.interaction === "disabled"
      ? "disabled"
      : parent.interaction === "readOnly" || child.interaction === "readOnly"
        ? "readOnly"
        : "enabled";
  return {
    visible: parent.visible && child.visible,
    interaction,
  };
};

const DEFAULT_STATE: ResolvedConditionalUiState = {
  visible: true,
  interaction: "enabled",
};

export const FormFields = ({
  errors,
  formData,
  schema,
  uiSchema,
  formContext,
  isFormLocked,
}: {
  errors: FormattedFormValidationWarning[] | null;
  formData: object;
  schema: RJSFSchema;
  uiSchema: UiSchema;
  formContext?: RootBudgetFormContext;
  isFormLocked?: boolean;
}) => {
  let requiredFieldPaths: string[];
  try {
    requiredFieldPaths = getRequiredProperties(schema);
  } catch (error: unknown) {
    console.error(error);
    return (
      <Alert data-testid="alert" type="error" heading="Error" headingLevel="h4">
        Error rendering form
      </Alert>
    );
  }

  const renderField = (
    node: UiSchemaField | UiSchemaFieldList,
    state: ResolvedConditionalUiState,
  ): JSX.Element | null => {
    const definition = "definition" in node ? node.definition : undefined;
    const requiredField = Boolean(
      node.type !== "fieldList" &&
      (isFieldRequired(
        node.definition || node.schema?.title || "",
        requiredFieldPaths,
      ) ||
        (typeof definition === "string" &&
          formContext?.activeConditionalRequiredPaths?.includes(
            jsonSchemaPointerToPath(definition),
          ))),
    );
    const widgetConfig = getFieldConfig({
      uiFieldObject: node,
      formSchema: schema,
      errors: errors ?? null,
      formData,
      requiredField,
    });
    const conditionReadOnly = state.interaction === "readOnly";
    return renderWidget({
      type: widgetConfig.type,
      props: {
        ...widgetConfig.props,
        ...(node.type === "null" ? { updateOnInput: true } : {}),
        disabled:
          Boolean(widgetConfig.props.disabled) ||
          state.interaction === "disabled" ||
          (conditionReadOnly && !supportsNativeReadOnly(widgetConfig.type)),
        readOnly: Boolean(widgetConfig.props.readOnly) || conditionReadOnly,
        formContext,
        isFormLocked,
      },
      definition: "definition" in node ? node.definition : undefined,
    });
  };

  const renderNodes = (
    nodes: UiSchema,
    parentState: ResolvedConditionalUiState,
  ): JSX.Element[] => {
    if (!Array.isArray(nodes)) {
      throw new Error("top level UI Schema element must be an array");
    }

    return nodes.flatMap((node) => {
      const state = combineConditionalState(
        parentState,
        resolveConditionalUiState(node.conditional, { rootData: formData }),
      );
      if (node.type === "section") {
        const sectionFields = renderNodes(node.children, state);
        const section = (
          <React.Fragment key={node.name}>
            {wrapSection({
              label: node.label,
              fieldName: node.name,
              sectionFields: <>{sectionFields}</>,
              description: node.description,
            })}
          </React.Fragment>
        );
        return state.visible
          ? [section]
          : [
              <div key={node.name} hidden aria-hidden="true">
                {section}
              </div>,
            ];
      }

      if (!isRenderableFieldNode(node)) {
        throw new Error("child field missing definition and schema");
      }
      const field = renderField(node, state);
      if (!field) {
        return [];
      }
      const nodeKey =
        node.name ??
        ("definition" in node ? node.definition?.toString() : undefined);
      return state.visible
        ? [<React.Fragment key={nodeKey}>{field}</React.Fragment>]
        : [
            <div key={nodeKey} hidden aria-hidden="true">
              {field}
            </div>,
          ];
    });
  };

  try {
    return renderNodes(uiSchema, DEFAULT_STATE);
  } catch (error: unknown) {
    console.error(error);
    return (
      <Alert data-testid="alert" type="error" heading="Error" headingLevel="h4">
        Error rendering form
      </Alert>
    );
  }
};
