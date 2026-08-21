type JsonRecord = Record<string, unknown>;

type DecimalValue = {
  units: bigint;
  scale: number;
  negative: boolean;
};

type QuantizedCents = {
  cents: bigint;
  negativeZero: boolean;
};

type CalculationRule = {
  path: string[];
  order: number;
  sequence: number;
  config: JsonRecord;
};

export type ClientCalculationRuleSchema = Record<string, unknown>;

export type ClientCalculationResult = {
  formData: JsonRecord;
  errors: string[];
};

const CALCULATION_RULE_NAMES = new Set([
  "sum_monetary",
  "multiply_by_percentage",
  "subtract_monetary",
]);

export const hasClientCalculationRules = (
  ruleSchema?: ClientCalculationRuleSchema | null,
): boolean => {
  if (!ruleSchema) {
    return false;
  }

  return Object.entries(ruleSchema).some(([key, value]) => {
    if (key === "gg_pre_population" && isJsonRecord(value)) {
      return (
        typeof value.rule === "string" && CALCULATION_RULE_NAMES.has(value.rule)
      );
    }
    return isJsonRecord(value) && hasClientCalculationRules(value);
  });
};

const PATH_TOKEN_PATTERN = /^(.+?)(?:\[([*]|\d+)])?$/;
const MONETARY_PATTERN = /^-?(?:\d+(?:\.\d+)?|\.\d+)$/;
const RELATIVE_PATH_PREFIX = "@THIS.";
const PARENT_PATH_PREFIX = "@PARENT.";

const isJsonRecord = (value: unknown): value is JsonRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const cloneJsonValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return (value as unknown[]).map(cloneJsonValue);
  }
  if (isJsonRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, nestedValue]) => [
        key,
        cloneJsonValue(nestedValue),
      ]),
    );
  }
  return value;
};

const pow10 = (exponent: number): bigint => {
  let result = BigInt(1);
  for (let index = 0; index < exponent; index += 1) {
    result *= BigInt(10);
  }
  return result;
};

const parseDecimal = (value: unknown): DecimalValue | null => {
  if (typeof value !== "string" || !MONETARY_PATTERN.test(value)) {
    return null;
  }

  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = ""] = unsigned.split(".");
  const units = BigInt(`${whole || "0"}${fraction}`);

  return {
    units: negative ? -units : units,
    scale: fraction.length,
    negative,
  };
};

const addDecimals = (
  left: DecimalValue,
  right: DecimalValue,
  subtractRight = false,
): DecimalValue => {
  const scale = Math.max(left.scale, right.scale);
  const leftUnits = left.units * pow10(scale - left.scale);
  const rightUnits = right.units * pow10(scale - right.scale);

  const units = subtractRight ? leftUnits - rightUnits : leftUnits + rightUnits;
  const effectiveRightNegative = subtractRight
    ? !right.negative
    : right.negative;
  return {
    units,
    scale,
    negative:
      units < BigInt(0) ||
      (units === BigInt(0) && left.negative && effectiveRightNegative),
  };
};

const quantizeToCents = ({
  units,
  scale,
  negative,
}: DecimalValue): QuantizedCents => {
  if (scale <= 2) {
    return {
      cents: units * pow10(2 - scale),
      negativeZero: negative && units === BigInt(0),
    };
  }

  const divisor = pow10(scale - 2);
  const absoluteUnits = units < BigInt(0) ? -units : units;
  let cents = absoluteUnits / divisor;
  const remainder = absoluteUnits % divisor;

  // Python Decimal.quantize uses ROUND_HALF_EVEN by default. On an exact tie,
  // round only when the retained cents digit is odd.
  if (
    remainder * BigInt(2) > divisor ||
    (remainder * BigInt(2) === divisor && cents % BigInt(2) !== BigInt(0))
  ) {
    cents += BigInt(1);
  }

  const isNegative = units < BigInt(0) || (units === BigInt(0) && negative);
  return {
    cents: isNegative ? -cents : cents,
    negativeZero: isNegative && cents === BigInt(0),
  };
};

const formatCents = ({ cents, negativeZero }: QuantizedCents): string => {
  const negative = cents < BigInt(0) || negativeZero;
  const absolute = negative ? -cents : cents;
  const whole = absolute / BigInt(100);
  const fraction = String(absolute % BigInt(100)).padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${fraction}`;
};

const parsePathToken = (
  token: string,
): { property: string; index?: number | "*" } | null => {
  const match = PATH_TOKEN_PATTERN.exec(token);
  if (!match || match[1].includes("[") || match[1].includes("]")) {
    return null;
  }

  const [, property, rawIndex] = match;
  if (rawIndex === undefined) {
    return { property };
  }
  return {
    property,
    index: rawIndex === "*" ? "*" : Number(rawIndex),
  };
};

const getPathValues = (data: JsonRecord, path: string[]): unknown[] => {
  let currentValues: unknown[] = [data];

  for (const rawToken of path) {
    const token = parsePathToken(rawToken);
    if (!token) {
      return [];
    }

    const nextValues: unknown[] = [];
    currentValues.forEach((currentValue) => {
      if (!isJsonRecord(currentValue)) {
        return;
      }

      const propertyValue = currentValue[token.property];
      if (token.index === undefined) {
        if (propertyValue !== undefined && propertyValue !== null) {
          nextValues.push(propertyValue);
        }
        return;
      }

      if (!Array.isArray(propertyValue)) {
        return;
      }
      const arrayValue = propertyValue as unknown[];

      if (token.index === "*") {
        arrayValue.forEach((item) => nextValues.push(item));
      } else if (token.index < arrayValue.length) {
        const indexedValue: unknown = arrayValue[token.index];
        if (indexedValue !== undefined && indexedValue !== null) {
          nextValues.push(indexedValue);
        }
      }
    });
    currentValues = nextValues;
  }

  return currentValues;
};

const resolveOperandPath = (
  targetPath: string[],
  operandPath: string,
): string[] => {
  if (operandPath.startsWith(RELATIVE_PATH_PREFIX)) {
    return [
      ...targetPath.slice(0, -1),
      ...operandPath.slice(RELATIVE_PATH_PREFIX.length).split("."),
    ];
  }
  if (operandPath.startsWith(PARENT_PATH_PREFIX)) {
    if (targetPath.length < 2) {
      return [];
    }
    return [
      ...targetPath.slice(0, -2),
      ...operandPath.slice(PARENT_PATH_PREFIX.length).split("."),
    ];
  }
  return operandPath.split(".");
};

const getOperandValues = (
  data: JsonRecord,
  targetPath: string[],
  operandPath: string,
): unknown[] => {
  const values: unknown[] = [];
  getPathValues(data, resolveOperandPath(targetPath, operandPath)).forEach(
    (value) => {
      if (Array.isArray(value)) {
        (value as unknown[]).forEach((item) => values.push(item));
      } else {
        values.push(value);
      }
    },
  );
  return values;
};

const setPathValue = (
  data: JsonRecord,
  path: string[],
  value: unknown,
): boolean => {
  let current: JsonRecord = data;

  for (let index = 0; index < path.length; index += 1) {
    const token = parsePathToken(path[index]);
    if (!token || token.index === "*") {
      return false;
    }

    const isLast = index === path.length - 1;
    if (token.index === undefined) {
      if (isLast) {
        current[token.property] = value;
        return true;
      }
      if (!isJsonRecord(current[token.property])) {
        if (current[token.property] !== undefined) {
          return false;
        }
        current[token.property] = {};
      }
      current = current[token.property] as JsonRecord;
      continue;
    }

    const propertyValue = current[token.property];
    if (!Array.isArray(propertyValue) || token.index >= propertyValue.length) {
      return false;
    }
    if (isLast) {
      propertyValue[token.index] = value;
      return true;
    }
    if (!isJsonRecord(propertyValue[token.index])) {
      return false;
    }
    current = propertyValue[token.index] as JsonRecord;
  }

  return false;
};

const sumValues = (values: unknown[]): DecimalValue =>
  values.reduce<DecimalValue>(
    (total, value) => {
      const parsed = parseDecimal(value);
      return parsed ? addDecimals(total, parsed) : total;
    },
    { units: BigInt(0), scale: 0, negative: false },
  );

const evaluateRule = (
  data: JsonRecord,
  rule: CalculationRule,
): string | null => {
  const ruleName = rule.config.rule;

  if (ruleName === "sum_monetary" || ruleName === "subtract_monetary") {
    const fields = rule.config.fields;
    if (
      !Array.isArray(fields) ||
      !fields.every((field) => typeof field === "string")
    ) {
      return null;
    }

    if (ruleName === "sum_monetary") {
      const total = sumValues(
        fields.flatMap((field) => getOperandValues(data, rule.path, field)),
      );
      return formatCents(quantizeToCents(total));
    }

    const result = fields.reduce<DecimalValue>(
      (total, field, index) => {
        const fieldTotal = sumValues(getOperandValues(data, rule.path, field));
        return addDecimals(total, fieldTotal, index > 0);
      },
      { units: BigInt(0), scale: 0, negative: false },
    );
    return formatCents(quantizeToCents(result));
  }

  if (ruleName === "multiply_by_percentage") {
    const amountPath = rule.config.amount;
    const percentagePath = rule.config.percentage;
    if (typeof amountPath !== "string" || typeof percentagePath !== "string") {
      return null;
    }

    const amountValue = getOperandValues(data, rule.path, amountPath)[0];
    const percentageValue = getOperandValues(
      data,
      rule.path,
      percentagePath,
    )[0];
    const amount =
      amountValue === undefined ? parseDecimal("0") : parseDecimal(amountValue);
    const percentage = percentageValue === undefined ? 0 : percentageValue;

    if (
      !amount ||
      typeof percentage !== "number" ||
      !Number.isInteger(percentage)
    ) {
      return null;
    }

    return formatCents(
      quantizeToCents({
        units: amount.units * BigInt(percentage),
        scale: amount.scale + 2,
        negative: amount.negative !== percentage < 0,
      }),
    );
  }

  return null;
};

const collectCalculationRules = (
  ruleSchema: JsonRecord,
  data: JsonRecord,
  path: string[],
  rules: CalculationRule[],
  errors: string[],
): void => {
  if (ruleSchema.gg_type === "array") {
    if (path.length === 0) {
      errors.push("A root rule schema cannot be an array");
      return;
    }

    const arrayValue = getPathValues(data, path)[0];
    if (arrayValue === undefined) {
      return;
    }
    if (!Array.isArray(arrayValue)) {
      errors.push(
        `Rule path ${path.join(".")} is marked as an array but has non-array data`,
      );
      return;
    }

    const nestedSchema = { ...ruleSchema };
    delete nestedSchema.gg_type;
    arrayValue.forEach((_, index) => {
      const indexedPath = [...path];
      indexedPath[indexedPath.length - 1] = `${indexedPath.at(-1)}[${index}]`;
      collectCalculationRules(nestedSchema, data, indexedPath, rules, errors);
    });
    return;
  }

  Object.entries(ruleSchema).forEach(([key, value]) => {
    if (key === "gg_pre_population" && isJsonRecord(value)) {
      const ruleName = value.rule;
      if (
        typeof ruleName === "string" &&
        CALCULATION_RULE_NAMES.has(ruleName)
      ) {
        rules.push({
          path,
          order: typeof value.order === "number" ? value.order : 1,
          sequence: rules.length,
          config: value,
        });
      }
      return;
    }

    if (isJsonRecord(value) && !key.startsWith("gg_")) {
      collectCalculationRules(value, data, [...path, key], rules, errors);
    }
  });
};

export const evaluateClientCalculations = (
  formData: object,
  ruleSchema?: ClientCalculationRuleSchema | null,
): ClientCalculationResult => {
  const data = cloneJsonValue(formData) as JsonRecord;
  const errors: string[] = [];
  if (!ruleSchema) {
    return { formData: data, errors };
  }

  const rules: CalculationRule[] = [];
  collectCalculationRules(ruleSchema, data, [], rules, errors);
  rules
    .sort(
      (left, right) =>
        left.order - right.order || left.sequence - right.sequence,
    )
    .forEach((rule) => {
      const value = evaluateRule(data, rule);
      if (value === null) {
        errors.push(
          `Unable to evaluate ${String(rule.config.rule)} at ${rule.path.join(".")}`,
        );
        return;
      }
      if (!setPathValue(data, rule.path, value)) {
        errors.push(
          `Unable to populate calculated value at ${rule.path.join(".")}`,
        );
      }
    });

  return { formData: data, errors };
};
