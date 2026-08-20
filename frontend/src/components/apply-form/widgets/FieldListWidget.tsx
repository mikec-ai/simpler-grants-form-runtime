import { RJSFSchema } from "@rjsf/utils/lib/types";
import {
  BroadlyDefinedWidgetValue,
  FieldListGroupItem,
  FieldListWidgetProps,
  FormattedFormValidationWarning,
  GeneralRecord,
  UswdsWidgetProps,
} from "src/types/applyForm/types";
import { isFieldRequired } from "src/utils/applyForm/applyFormUtils";
import {
  getFieldListChildErrors,
  getFieldListGroupErrors,
} from "src/utils/applyForm/fieldListHelpers";

import { useTranslations } from "next-intl";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Button } from "@trussworks/react-uswds";

import { USWDSIcon } from "src/components/core/USWDSIcon";
import { renderWidget } from "./WidgetRenderers";

/**
 * Path to this child field's value inside a single FieldList entry object.
 *
 * Flat fields use a one-item path:
 *   ["organization_name"] -> entry.organization_name
 *
 * Nested fields use multiple path parts:
 *   ["address", "street1"] -> entry.address.street1
 *
 * This is an array so the widget can read and update nested values without
 * flattening them into keys like "address--street1".
 */
type FieldListChangeParams = {
  entryId: string;
  /**
   * Path to the field being updated within the entry object.
   * Example: ["address", "street1"] updates entry.address.street1.
   */
  storagePath: string[];
  nextValue: unknown;
};

type FieldListEntry = {
  entryId: string;
  value: GeneralRecord;
};

const FIELD_LIST_INDEX_TOKEN = "~~index~~";
const FIELD_LIST_HEADING_ELEMENTS = {
  1: "h1",
  2: "h2",
  3: "h3",
  4: "h4",
  5: "h5",
  6: "h6",
} as const;

function FieldListHeading({
  level,
  id,
  className,
  children,
}: {
  level: number;
  id: string;
  className?: string;
  children: ReactNode;
}) {
  const boundedLevel = Math.max(level, 1);
  const Heading =
    boundedLevel <= 6
      ? FIELD_LIST_HEADING_ELEMENTS[
          boundedLevel as keyof typeof FIELD_LIST_HEADING_ELEMENTS
        ]
      : undefined;

  if (Heading) {
    return (
      <Heading id={id} className={className}>
        {children}
      </Heading>
    );
  }

  return (
    <div id={id} className={className} role="heading" aria-level={boundedLevel}>
      {children}
    </div>
  );
}

/**
 * Builds the initial entries rendered by FieldList.
 *
 * Saved form data is stored as `GeneralRecord[]`, but the widget needs stable
 * client-side entry ids so React can preserve each entry's local state when
 * entries are added or removed. The entry ids are only used for rendering and
 * are stripped before values are sent back to the parent form.
 *
 * If the schema defines `minItems`, blank entries are appended so the UI shows
 * the required minimum number of entries.
 */
const normalizeFieldListEntries = ({
  value,
  minItems,
}: {
  value: GeneralRecord[] | undefined;
  minItems?: number;
}): FieldListEntry[] => {
  const startingEntries = Array.isArray(value)
    ? value
        .filter((entryValue): entryValue is GeneralRecord => {
          return typeof entryValue === "object" && entryValue !== null;
        })
        .map((entryValue, entryIndex) => ({
          entryId: `field-list-entry-${entryIndex}`,
          value: entryValue,
        }))
    : [];

  const minimumEntryCount = minItems ?? 0;

  if (startingEntries.length >= minimumEntryCount) {
    return startingEntries;
  }

  const missingEntryCount = minimumEntryCount - startingEntries.length;

  return [
    ...startingEntries,
    ...Array.from({ length: missingEntryCount }, (_, missingEntryIndex) => ({
      entryId: `field-list-entry-${startingEntries.length + missingEntryIndex}`,
      value: {},
    })),
  ];
};

/**
 * Replaces the FieldList entry index placeholder with the actual entry index.
 *
 * Example:
 *   contact_people_test[~~index~~]--first_name
 *
 * becomes:
 *   contact_people_test[0]--first_name
 */
const replaceFieldListIndexPlaceholder = ({
  baseId,
  entryIndex,
}: {
  baseId: string;
  entryIndex: number;
}): string => {
  return baseId.replace(FIELD_LIST_INDEX_TOKEN, String(entryIndex));
};

/**
 * Returns a new entry array with one additional empty entry appended.
 */
const addFieldListEntry = ({
  entries,
  entryId,
}: {
  entries: FieldListEntry[];
  entryId: string;
}): FieldListEntry[] => {
  return [
    ...entries,
    {
      entryId,
      value: {},
    },
  ];
};

/**
 * Narrows entry values into the value shapes accepted by the widget renderer.
 *
 * Child widgets rendered inside FieldList still expect standard widget values
 * such as:
 * - string
 * - number
 * - boolean
 * - string[]
 * - object
 *
 * Since entry object access returns `unknown`, this helper safely converts the
 * value into a `BroadlyDefinedWidgetValue` when possible.
 */
const toBroadlyDefinedWidgetValue = (
  value: unknown,
): BroadlyDefinedWidgetValue | undefined => {
  if (value === undefined) {
    return undefined;
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }

  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return value;
  }

  if (
    Array.isArray(value) &&
    value.every(
      (item) =>
        typeof item === "object" && item !== null && !Array.isArray(item),
    )
  ) {
    return value as GeneralRecord[];
  }

  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    return value as GeneralRecord;
  }

  return undefined;
};

/**
 * Removes FieldList-only metadata before sending values back to the parent form.
 *
 * The parent form and save pipeline expect FieldList data as `GeneralRecord[]`.
 * `entryId` is only used locally by the widget for stable React rendering.
 */
const getFieldListValues = (entries: FieldListEntry[]): GeneralRecord[] => {
  return entries.map((entry) => entry.value);
};

/**
 * Reads a nested value from a FieldList entry using the storage path generated
 * from the child field definition.
 */
const getValueAtPath = ({
  value,
  path,
}: {
  value: GeneralRecord;
  path: string[];
}): unknown => {
  return path.reduce<unknown>((currentValue, pathPart) => {
    if (
      typeof currentValue === "object" &&
      currentValue !== null &&
      !Array.isArray(currentValue)
    ) {
      return (currentValue as GeneralRecord)[pathPart];
    }

    return undefined;
  }, value);
};

/**
 * Writes a child value into a FieldList entry while preserving nested object
 * structure, for example address.street1.
 */
const setValueAtPath = ({
  value,
  path,
  nextValue,
}: {
  value: GeneralRecord;
  path: string[];
  nextValue: BroadlyDefinedWidgetValue | undefined;
}): GeneralRecord => {
  const [currentPathPart, ...remainingPathParts] = path;

  if (!currentPathPart) {
    return value;
  }

  if (remainingPathParts.length === 0) {
    return {
      ...value,
      [currentPathPart]: nextValue,
    };
  }

  const currentNestedValue = value[currentPathPart];
  const nestedValue =
    typeof currentNestedValue === "object" &&
    currentNestedValue !== null &&
    !Array.isArray(currentNestedValue)
      ? (currentNestedValue as GeneralRecord)
      : {};

  return {
    ...value,
    [currentPathPart]: setValueAtPath({
      value: nestedValue,
      path: remainingPathParts,
      nextValue,
    }),
  };
};

function FieldListEntry({
  entryId,
  entryIndex,
  entryLabel,
  entryValue,
  canDeleteEntry,
  handleDeleteEntry,
  handleFieldChange,
  isInteractionDisabled,
  rawErrors,
  fieldListPath,
  groupDefinition,
  requiredFields,
  minItemsHeading,
  minItemsHelperText,
  idPrefix,
  formContext,
  headingLevel,
  ancestorContextLabel,
}: {
  entryId: string;
  entryIndex: number;
  entryLabel: string;
  entryValue: GeneralRecord;
  canDeleteEntry: boolean;
  handleDeleteEntry: (entryId: string) => void;
  handleFieldChange: (params: FieldListChangeParams) => void;
  isInteractionDisabled: boolean;
  rawErrors?: FormattedFormValidationWarning[];
  fieldListPath: string;
  groupDefinition: FieldListGroupItem[];
  requiredFields?: string[];
  minItemsHeading?: string;
  minItemsHelperText?: string;
  idPrefix?: string;
  formContext?: FieldListWidgetProps["formContext"];
  headingLevel: number;
  ancestorContextLabel?: string;
}) {
  const t = useTranslations("Application.applyForm.fieldListWidget");
  const fieldListId = fieldListPath.replace("$.", "").replace(/\W/g, "-");
  const entryHeadingId = `${fieldListId}-entry-${entryIndex + 1}-heading`;
  const entryContextLabel = ancestorContextLabel
    ? `${ancestorContextLabel}, ${entryLabel} ${entryIndex + 1}`
    : `${entryLabel} ${entryIndex + 1}`;

  return (
    <div className="field-list-widget__entry padding-y-2 padding-bottom-3">
      <div className="field-list-widget__entry-header margin-bottom-2">
        <FieldListHeading
          level={headingLevel + 1}
          id={entryHeadingId}
          className="margin-bottom-2"
        >
          {entryLabel} {entryIndex + 1}
        </FieldListHeading>
      </div>

      {groupDefinition.map((groupItem: FieldListGroupItem) => {
        const localGeneratedId = replaceFieldListIndexPlaceholder({
          baseId: groupItem.baseId,
          entryIndex,
        });
        const generatedId = idPrefix
          ? `${idPrefix}--${localGeneratedId}`
          : localGeneratedId;

        // The full schema-derived id is required here. Sibling branches can
        // legitimately end in the same property name (for example,
        // direct_costs.periods and indirect_costs.periods).
        const childKey = groupItem.baseId;

        const currentRawValue = getValueAtPath({
          value: entryValue,
          path: groupItem.storagePath,
        });

        if (groupItem.widget === "FieldList") {
          const nestedFieldListPath = `${fieldListPath}[${entryIndex}].${groupItem.storagePath.join(".")}`;
          const nestedListIdSuffix = `--${groupItem.storagePath.at(-1) ?? groupItem.fieldListProps.name}`;
          const nestedIdPrefix = generatedId.endsWith(nestedListIdSuffix)
            ? generatedId.slice(0, -nestedListIdSuffix.length)
            : generatedId;
          const nestedValue = Array.isArray(currentRawValue)
            ? currentRawValue.filter(
                (item): item is GeneralRecord =>
                  typeof item === "object" &&
                  item !== null &&
                  !Array.isArray(item),
              )
            : undefined;

          return (
            <FieldListWidget
              {...groupItem.fieldListProps}
              id={generatedId}
              key={`${entryId}-${childKey}`}
              idPrefix={nestedIdPrefix}
              headingLevel={headingLevel + 2}
              ancestorContextLabel={entryContextLabel}
              additionalDescribedById={entryHeadingId}
              fieldListPath={nestedFieldListPath}
              value={nestedValue}
              rawErrors={rawErrors}
              disabled={isInteractionDisabled}
              readOnly={isInteractionDisabled}
              isFormLocked={isInteractionDisabled}
              formContext={formContext}
              onChange={(nextValue) => {
                handleFieldChange({
                  entryId,
                  storagePath: groupItem.storagePath,
                  nextValue,
                });
              }}
            />
          );
        }

        const isRequired = isFieldRequired(
          groupItem.definition,
          requiredFields ?? [],
        );

        const childErrors = getFieldListChildErrors({
          rawErrors,
          fieldListPath,
          entryIndex,
          storagePath: groupItem.storagePath,
          childDefinition: groupItem.definition,
        });

        const currentValue = toBroadlyDefinedWidgetValue(currentRawValue);

        const childWidgetProps: UswdsWidgetProps = {
          ...groupItem.generalProps,
          schema: groupItem.generalProps.schema as RJSFSchema,
          id: generatedId,
          name: generatedId,
          key: `${entryId}-${childKey}`,
          value: currentValue,
          rawErrors: childErrors,
          required: isRequired,
          updateOnInput: true,
          additionalDescribedById: entryHeadingId,
          disabled:
            isInteractionDisabled || Boolean(groupItem.generalProps.disabled),
          readOnly:
            isInteractionDisabled || Boolean(groupItem.generalProps.readOnly),
          isFormLocked:
            isInteractionDisabled ||
            Boolean(groupItem.generalProps.isFormLocked),
          onChange: (nextValue) => {
            handleFieldChange({
              entryId,
              storagePath: groupItem.storagePath,
              nextValue,
            });
          },
        };

        return (
          <Fragment key={`${entryId}-${childKey}`}>
            {renderWidget({
              type: groupItem.widget,
              props: childWidgetProps,
            })}
          </Fragment>
        );
      })}

      <div className="field-list-widget__entry-controls margin-top-2 padding-top-2 display-flex flex-align-start flex-justify-between">
        {!canDeleteEntry && (minItemsHeading || minItemsHelperText) ? (
          <div>
            {minItemsHeading ? (
              <p className="text-bold margin-bottom-05">{minItemsHeading}</p>
            ) : null}
            {minItemsHelperText ? (
              <p className="usa-hint margin-top-0 margin-bottom-0">
                {minItemsHelperText}
              </p>
            ) : null}
          </div>
        ) : (
          <div />
        )}

        <Button
          type="button"
          onClick={() => handleDeleteEntry(entryId)}
          disabled={!canDeleteEntry}
          className="button--danger margin-left-auto"
          outline
          aria-label={`${t("deleteEntry")}: ${entryContextLabel}`}
        >
          <USWDSIcon name="delete" />
          {t("deleteEntry")}
        </Button>
      </div>
    </div>
  );
}

function FieldListWidget(widgetProps: FieldListWidgetProps) {
  const {
    id,
    label,
    description,
    additionalDescribedById,
    name,
    minItems,
    minItemsHeading,
    minItemsHelperText,
    maxItems,
    maxItemsHeading,
    maxItemsHelperText,
    groupDefinition,
    value,
    onChange,
    disabled,
    readOnly,
    isFormLocked,
    rawErrors,
    fieldListPath: suppliedFieldListPath,
    idPrefix,
    headingLevel = 3,
    ancestorContextLabel,
  } = widgetProps;
  const t = useTranslations("Application.applyForm.fieldListWidget");
  const fieldListPath = suppliedFieldListPath ?? `$.${name}`;
  const groupErrors = getFieldListGroupErrors({
    rawErrors,
    fieldListPath,
  });

  /**
   * FieldList manages entry add/remove behavior locally so the UI updates
   * immediately during editing.
   *
   * The entries are rehydrated from the incoming `value` prop so the widget
   * stays aligned with saved form data after save / reload.
   */
  const initialFieldListEntries = useMemo(
    () =>
      normalizeFieldListEntries({
        value,
        minItems,
      }),
    [value, minItems],
  );

  const [entries, setEntries] = useState<FieldListEntry[]>(
    initialFieldListEntries,
  );
  const entriesRef = useRef<FieldListEntry[]>(initialFieldListEntries);
  const nextEntryIdRef = useRef(initialFieldListEntries.length);
  const externalValueSnapshotRef = useRef(
    JSON.stringify({ value: value ?? [], minItems }),
  );

  useEffect(() => {
    const externalValueSnapshot = JSON.stringify({
      value: value ?? [],
      minItems,
    });
    if (externalValueSnapshot === externalValueSnapshotRef.current) {
      return;
    }
    externalValueSnapshotRef.current = externalValueSnapshot;
    const currentEntries = entriesRef.current;
    const synchronizedEntries = initialFieldListEntries.map(
      (incomingEntry, entryIndex) => ({
        entryId:
          currentEntries[entryIndex]?.entryId ??
          `field-list-entry-${nextEntryIdRef.current++}`,
        value: incomingEntry.value,
      }),
    );
    entriesRef.current = synchronizedEntries;
    setEntries(synchronizedEntries);
  }, [initialFieldListEntries, minItems, value]);

  const onFieldListEntryDelete =
    widgetProps.formContext?.widgetSupport?.onFieldListEntryDelete;

  const markFormDirty = widgetProps.formContext?.widgetSupport?.markFormDirty;
  const onFieldListChange =
    widgetProps.formContext?.widgetSupport?.onFieldListChange;

  const isInteractionDisabled = Boolean(disabled || readOnly || isFormLocked);
  const minimumEntryCount = minItems ?? 0;
  const maximumEntryCount = maxItems;

  const isAtMinimumEntryCount = entries.length <= minimumEntryCount;
  const isAtMaximumEntryCount =
    maximumEntryCount !== undefined && entries.length >= maximumEntryCount;

  const canAddEntry = !isInteractionDisabled && !isAtMaximumEntryCount;
  const canDeleteEntry = !isInteractionDisabled && !isAtMinimumEntryCount;

  const resolvedMinItemsHeading =
    minItemsHeading ?? "Would you like to delete this field?";

  const resolvedMinItemsHelperText =
    minItemsHelperText ?? `There is a minimum count of ${minimumEntryCount}.`;

  const resolvedEntryLabel = label ?? "entry";

  const resolvedMaxItemsHeading =
    maxItemsHeading ?? "Do you have another entry to add?";

  const resolvedMaxItemsHelperText =
    maxItemsHelperText ??
    `You have reached the maximum count of ${maximumEntryCount} entries.`;

  /**
   * Applies updates to FieldList entries.
   *
   * This is the central update path for:
   * - child field edits
   * - entry additions
   * - entry deletions
   *
   * Also marks the parent form dirty so existing unsaved-change
   * protections apply to FieldList interactions.
   */
  const handleEntriesChange = useCallback(
    (
      getNextEntries: (previousEntries: FieldListEntry[]) => FieldListEntry[],
    ): void => {
      const nextEntries = getNextEntries(entriesRef.current);
      entriesRef.current = nextEntries;
      setEntries(nextEntries);
      onChange?.(getFieldListValues(nextEntries));
      markFormDirty?.();
    },
    [markFormDirty, onChange],
  );

  const handleAddEntry = useCallback((): void => {
    const currentEntries = entriesRef.current;

    if (
      maximumEntryCount !== undefined &&
      currentEntries.length >= maximumEntryCount
    ) {
      return;
    }

    handleEntriesChange((previousEntries) =>
      addFieldListEntry({
        entries: previousEntries,
        entryId: `field-list-entry-${nextEntryIdRef.current++}`,
      }),
    );
    onFieldListChange?.();
  }, [handleEntriesChange, maximumEntryCount, onFieldListChange]);

  const handleDeleteEntry = useCallback(
    (entryId: string): void => {
      const currentEntries = entriesRef.current;

      if (currentEntries.length <= minimumEntryCount) {
        return;
      }

      const entryIndex = currentEntries.findIndex(
        (entry) => entry.entryId === entryId,
      );

      if (entryIndex === -1) {
        return;
      }

      onFieldListEntryDelete?.(fieldListPath, entryIndex);

      handleEntriesChange((previousEntries) =>
        previousEntries.filter((entry) => entry.entryId !== entryId),
      );
      onFieldListChange?.();
    },
    [
      fieldListPath,
      handleEntriesChange,
      minimumEntryCount,
      onFieldListEntryDelete,
      onFieldListChange,
    ],
  );

  /**
   * Handles updates to a single field within a specific row.
   *
   * Receives raw `unknown` values from child widgets and normalizes them
   * before updating the row state. Ensures updates are scoped to the correct
   * row and field, and preserves immutability of the entries array.
   */
  const handleFieldChange = useCallback(
    ({ entryId, storagePath, nextValue }: FieldListChangeParams): void => {
      const normalizedNextValue = toBroadlyDefinedWidgetValue(nextValue);

      handleEntriesChange((previousEntries) =>
        previousEntries.map((previousEntry) => {
          if (previousEntry.entryId !== entryId) {
            return previousEntry;
          }

          return {
            ...previousEntry,
            value: setValueAtPath({
              value: previousEntry.value,
              path: storagePath,
              nextValue: normalizedNextValue,
            }),
          };
        }),
      );
    },
    [handleEntriesChange],
  );

  return (
    <div
      id={id}
      role="group"
      aria-labelledby={label ? `${id}-heading` : undefined}
      aria-describedby={additionalDescribedById}
      className="field-list-widget border border-base-lighter radius-md padding-2 margin-y-2"
    >
      {label ? (
        <FieldListHeading level={headingLevel} id={`${id}-heading`}>
          {label}
        </FieldListHeading>
      ) : null}
      {description ? <p>{description}</p> : null}

      {groupErrors.length > 0 ? (
        <ul className="usa-error-message margin-top-1" aria-live="polite">
          {groupErrors.map((error) => (
            <li key={`${error.field}-${error.message}`}>
              {error.formatted ?? error.message}
            </li>
          ))}
        </ul>
      ) : null}

      {entries.map((entry, entryIndex) => {
        return (
          <FieldListEntry
            key={entry.entryId}
            entryId={entry.entryId}
            entryLabel={resolvedEntryLabel}
            entryValue={entry.value}
            entryIndex={entryIndex}
            canDeleteEntry={canDeleteEntry}
            handleDeleteEntry={handleDeleteEntry}
            handleFieldChange={handleFieldChange}
            isInteractionDisabled={isInteractionDisabled}
            groupDefinition={groupDefinition}
            rawErrors={rawErrors}
            fieldListPath={fieldListPath}
            requiredFields={widgetProps.requiredFields}
            minItemsHeading={resolvedMinItemsHeading}
            minItemsHelperText={resolvedMinItemsHelperText}
            idPrefix={idPrefix}
            formContext={widgetProps.formContext}
            headingLevel={headingLevel}
            ancestorContextLabel={ancestorContextLabel}
          />
        );
      })}

      {isAtMaximumEntryCount && (maxItemsHeading || maxItemsHelperText) ? (
        <div className="margin-top-1">
          {maxItemsHeading ? (
            <p className="text-bold margin-bottom-05">
              {resolvedMaxItemsHeading}
            </p>
          ) : null}
          {maxItemsHelperText ? (
            <p className="usa-hint margin-top-0">
              {resolvedMaxItemsHelperText}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="field-list-widget__controls padding-top-2 display-flex flex-align-start flex-justify-between">
        <div>
          <p className="text-bold margin-bottom-05">
            {resolvedMaxItemsHeading}
          </p>
          {isAtMaximumEntryCount ? (
            <p className="usa-hint margin-top-0 margin-bottom-0">
              {resolvedMaxItemsHelperText}
            </p>
          ) : null}
        </div>

        <Button
          className="margin-left-auto"
          type="button"
          onClick={handleAddEntry}
          disabled={!canAddEntry}
          outline
          aria-label={`${t("addEntry")}: ${resolvedEntryLabel}${ancestorContextLabel ? ` — ${ancestorContextLabel}` : ""}`}
        >
          <USWDSIcon name="add" />
          {t("addEntry")}
        </Button>
      </div>
    </div>
  );
}

export default FieldListWidget;
