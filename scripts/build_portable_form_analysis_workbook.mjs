#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.WORKSPACE_ROOT ?? path.resolve(HERE, "..");
const ANALYSIS_DIR = path.join(ROOT, "documentation", "form-analysis");
const OUTPUT_DIR = path.join(ROOT, "outputs", "declarative-composition-wave");
const OUTPUT = path.join(OUTPUT_DIR, "form-analysis.xlsx");
const REPO_OUTPUT = path.join(ANALYSIS_DIR, "form-analysis.xlsx");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let value = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        value += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        value += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(value);
      value = "";
    } else if (character === "\n") {
      row.push(value.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      value = "";
    } else {
      value += character;
    }
  }
  if (value.length > 0 || row.length > 0) {
    row.push(value.replace(/\r$/, ""));
    rows.push(row);
  }
  return rows;
}

function typed(value) {
  if (value === "True") return true;
  if (value === "False") return false;
  if (value !== "" && /^-?\d+(\.\d+)?$/.test(value)) return Number(value);
  return value;
}

async function csvRows(filename, columns) {
  const parsed = parseCsv(await fs.readFile(path.join(ANALYSIS_DIR, filename), "utf8"));
  const headers = parsed[0];
  const headerIndexes = new Map(headers.map((header, index) => [header, index]));
  const missing = columns.filter(({ source }) => !headerIndexes.has(source));
  if (missing.length > 0) {
    throw new Error(
      `${filename} is missing required columns: ${missing.map(({ source }) => source).join(", ")}`,
    );
  }
  return [
    columns.map(({ label }) => label),
    ...parsed
      .slice(1)
      .map((row) => columns.map(({ source }) => typed(row[headerIndexes.get(source)] ?? ""))),
  ];
}

const column = (source, label) => ({ source, label });

const COLORS = {
  navy: "#17324D",
  blue: "#2F6B8A",
  teal: "#1D7874",
  paleTeal: "#E5F2F1",
  paleBlue: "#EAF1F6",
  paleGold: "#FFF4D6",
  gold: "#D89B26",
  ink: "#203040",
  muted: "#64748B",
  line: "#D7E0E7",
  white: "#FFFFFF",
};

const DISPLAY_NAMES = {
  KeyContacts: "Key Contacts",
  RRBudget: "R&R Budget (5-year)",
  RRBudget10: "R&R Budget (10-year)",
  RRMPBudget: "R&R Multi-Project Budget",
  RRSubawardBudget30: "R&R Subaward Budget (30 attachments)",
  SF424: "SF-424 Application",
};

function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function addDataSheet(workbook, name, rows, tableName, widths, percentColumns = []) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const lastColumn = columnName(rows[0].length - 1);
  const lastRow = rows.length;
  sheet.getRange(`A1:${lastColumn}${lastRow}`).values = rows;
  const header = sheet.getRange(`A1:${lastColumn}1`);
  header.format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: COLORS.navy },
  };
  header.format.rowHeight = 34;
  const body = sheet.getRange(`A2:${lastColumn}${lastRow}`);
  body.format = {
    font: { color: COLORS.ink },
    verticalAlignment: "top",
    borders: {
      bottom: { style: "thin", color: COLORS.line },
    },
  };
  body.format.rowHeight = 21;
  widths.forEach((width, index) => {
    sheet.getRange(`${columnName(index)}:${columnName(index)}`).format.columnWidth = width;
  });
  percentColumns.forEach((index) => {
    sheet.getRange(`${columnName(index)}2:${columnName(index)}${lastRow}`).format.numberFormat = "0.0%";
  });
  sheet.freezePanes.freezeRows(1);
  const table = sheet.tables.add(`A1:${lastColumn}${lastRow}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showBandedRows = true;
  table.showFilterButton = true;
  return sheet;
}

async function main() {
  const forms = await csvRows("forms.csv", [
    column("form_key", "Form Key"),
    column("form_name", "Form Name"),
    column("form_version", "Version"),
    column("semantic_question_occurrences", "Semantic Question Occurrences"),
    column("content_capture_mechanisms", "Content Capture Mechanisms"),
    column("semantic_mapping_status", "Semantic Mapping Status"),
    column("published_coverage_eligible", "Published Coverage Eligible"),
    column("production_ready", "Production Ready"),
  ]);
  const pairs = await csvRows("form-pairs.csv", [
    column("form_a", "Form A"),
    column("form_b", "Form B"),
    column("comparison_basis", "Comparison Basis"),
    column("proposed_similarity", "Role-qualified Proposed Similarity"),
    column("proposed_questions_in_common", "Role-qualified Questions in Common"),
    column("proposed_unique_questions", "Role-qualified Questions Across Pair"),
    column("form_a_proposed_coverage", "% of Form A Shared by Form B"),
    column("form_b_proposed_coverage", "% of Form B Shared by Form A"),
    column("template_proposed_similarity", "Question-template Similarity"),
    column("template_proposed_questions_in_common", "Question Templates in Common"),
    column("accepted_similarity", "Accepted Similarity"),
    column("accepted_questions_in_common", "Accepted Questions in Common"),
  ]);
  const questions = await csvRows("questions.csv", [
    column("question_id", "Question Template ID"),
    column("question_title", "Question"),
    column("schema_variant_count", "Validation Variants"),
    column("proposed_form_count", "Forms with Proposed Use"),
    column("accepted_form_count", "Forms with Accepted Use"),
    column("published_form_count", "Forms with Published Use"),
  ]);
  const roleQualifiedQuestions = await csvRows("role-qualified-questions.csv", [
    column("semantic_identity", "Role-qualified Semantic Identity"),
    column("question_id", "Question Template ID"),
    column("role", "Occurrence Role"),
    column("proposed_form_count", "Forms with Proposed Use"),
    column("accepted_form_count", "Forms with Accepted Use"),
    column("published_form_count", "Forms with Published Use"),
  ]);
  const associations = await csvRows("form-question-map.csv", [
    column("form_key", "Form Key"),
    column("question_id", "Question Template ID"),
    column("semantic_identity", "Role-qualified Semantic Identity"),
    column("schema_id", "Schema ID"),
    column("analysis_classification", "Analysis Classification"),
    column("role", "Role"),
    column("form_pointer", "Path in Form Schema"),
    column("mapping_status", "Mapping Status"),
    column("included_in_proposed_overlap", "Included in Proposed Overlap"),
    column("included_in_accepted_overlap", "Included in Accepted Overlap"),
    column("xml_path", "Path in Grants.gov XML"),
    column("type_source", "XML Type Source"),
    column("type", "XML Type"),
    column("xsd_source", "XSD Source Link"),
  ]);
  forms.slice(1).forEach((row) => {
    row[1] = DISPLAY_NAMES[row[0]] ?? row[1];
  });
  pairs.slice(1).forEach((row) => {
    row[0] = DISPLAY_NAMES[row[0]] ?? row[0];
    row[1] = DISPLAY_NAMES[row[1]] ?? row[1];
  });

  const workbook = Workbook.create();
  const overview = workbook.worksheets.add("Overview");
  overview.showGridLines = false;

  addDataSheet(workbook, "Forms", forms, "FormsTable", [18, 48, 11, 22, 22, 22, 20, 16]);
  addDataSheet(
    workbook,
    "Form Pairs",
    pairs,
    "FormPairsTable",
    [38, 38, 24, 20, 22, 22, 23, 23, 18, 20, 17, 22],
    [3, 6, 7, 8, 10],
  );
  addDataSheet(workbook, "Questions", questions, "QuestionsTable", [64, 52, 19, 23, 22, 22]);
  addDataSheet(
    workbook,
    "Role-qualified Questions",
    roleQualifiedQuestions,
    "RoleQualifiedQuestionsTable",
    [72, 58, 32, 23, 22, 22],
  );
  addDataSheet(
    workbook,
    "Form Question Map",
    associations,
    "FormQuestionMapTable",
    [24, 48, 72, 52, 25, 25, 58, 20, 23, 23, 58, 48, 24, 62],
  );

  overview.mergeCells("A1:H2");
  overview.getRange("A1").values = [["Declarative Form Reuse Analysis"]];
  overview.getRange("A1:H2").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 22 },
    verticalAlignment: "center",
  };
  overview.mergeCells("A3:H3");
  overview.getRange("A3").values = [[
    "Question-level analysis generated directly from the same portable declarations used to build the forms.",
  ]];
  overview.getRange("A3:H3").format = {
    fill: COLORS.paleBlue,
    font: { color: COLORS.ink, italic: true },
    verticalAlignment: "center",
  };

  const cards = [
    ["Forms in this implementation wave", "=COUNTA(Forms!A2:A200)"],
    ["Reusable question templates", "=COUNTA(Questions!A2:A500)"],
    ["Role-qualified semantic identities", "=COUNTA('Role-qualified Questions'!A2:A1000)"],
    ["Question occurrences", '=COUNTIF(\'Form Question Map\'!E2:E1000,"semantic_question")'],
  ];
  const cardRanges = ["A5:B7", "C5:D7", "E5:F7", "G5:H7"];
  cards.forEach(([label, formula], index) => {
    const range = overview.getRange(cardRanges[index]);
    range.format = {
      fill: index === 3 ? COLORS.paleGold : COLORS.paleTeal,
      borders: { preset: "outside", style: "thin", color: index === 3 ? COLORS.gold : COLORS.teal },
    };
    const startColumn = columnName(index * 2);
    const endColumn = columnName(index * 2 + 1);
    overview.mergeCells(`${startColumn}5:${endColumn}5`);
    overview.getRange(`${startColumn}5`).values = [[label]];
    overview.getRange(`${startColumn}5:${endColumn}5`).format = {
      font: { bold: true, color: COLORS.ink },
      wrapText: true,
      horizontalAlignment: "center",
      verticalAlignment: "center",
    };
    overview.mergeCells(`${startColumn}6:${endColumn}7`);
    overview.getRange(`${startColumn}6`).formulas = [[formula]];
    overview.getRange(`${startColumn}6:${endColumn}7`).format = {
      font: { bold: true, color: COLORS.navy, size: 24 },
      horizontalAlignment: "center",
      verticalAlignment: "center",
      numberFormat: "0",
    };
  });

  overview.mergeCells("A9:H9");
  overview.getRange("A9").values = [["How to read this workbook"]];
  overview.getRange("A9:H9").format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white, size: 14 },
    verticalAlignment: "center",
  };
  overview.getRange("A10:H15").values = [
    ["Forms", "One row per implemented portable form.", null, null, null, null, null, null],
    ["Form Pairs", "Role-qualified proposed overlap for every pair. Question-template overlap remains visible in separate columns.", null, null, null, null, null, null],
    ["Questions", "Reusable question/schema templates. A template may appear in several different roles.", null, null, null, null, null, null],
    ["Role-qualified Questions", "Conservative semantic identities combining each question template with its occurrence role.", null, null, null, null, null, null],
    ["Form Question Map", "Every form occurrence, its template, role-qualified identity, role, paths, and XML metadata.", null, null, null, null, null, null],
    ["Attachment mechanism", "A file-upload mechanism can capture many questions inside an attached document. It is retained in the map but excluded from question-overlap scores.", null, null, null, null, null, null],
  ];
  for (let row = 10; row <= 15; row += 1) {
    overview.mergeCells(`B${row}:H${row}`);
  }
  overview.getRange("A10:A15").format = {
    fill: COLORS.paleBlue,
    font: { bold: true, color: COLORS.navy },
    verticalAlignment: "top",
  };
  overview.getRange("B10:H15").format = {
    font: { color: COLORS.ink },
    wrapText: true,
    verticalAlignment: "top",
  };
  overview.getRange("A10:H15").format.borders = {
    bottom: { style: "thin", color: COLORS.line },
  };

  const sortedPairs = pairs.slice(1).sort((left, right) => right[3] - left[3]).slice(0, 8);
  overview.getRange("A18:C26").values = [
    ["Form Pair", "Proposed Similarity", "Questions in Common"],
    ...sortedPairs.map((row) => [`${row[0]} + ${row[1]}`, row[3], row[4]]),
  ];
  overview.getRange("A18:C18").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
  };
  overview.getRange("B19:B26").format.numberFormat = "0.0%";
  overview.getRange("J18:K26").values = [
    ["Form Pair", "Questions in Common"],
    ...sortedPairs.map((row) => [`${row[0]} + ${row[1]}`, row[4]]),
  ];
  const chart = overview.charts.add("bar", overview.getRange("J18:K26"));
  chart.title = "Questions shared by the highest-overlap pairs";
  chart.hasLegend = false;
  chart.xAxis = { numberFormatCode: "0", min: 0, max: 110 };
  chart.setPosition("E18", "L28");

  overview.getRange("A30:H32").merge();
  overview.getRange("A30").values = [[
    "Current boundary: every semantic mapping in this workbook is proposed, not accepted. The workbook demonstrates that implementation declarations can produce the requested analytical tables without a second manual mapping system.",
  ]];
  overview.getRange("A30:H32").format = {
    fill: COLORS.paleGold,
    font: { color: COLORS.ink, italic: true },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: COLORS.gold },
  };

  overview.freezePanes.freezeRows(3);
  overview.getRange("A:A").format.columnWidth = 40;
  overview.getRange("B:H").format.columnWidth = 18;
  overview.getRange("1:3").format.rowHeight = 28;
  overview.getRange("10:15").format.rowHeight = 34;
  overview.getRange("30:32").format.rowHeight = 28;

  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(OUTPUT);
  await xlsx.save(REPO_OUTPUT);

  for (const sheetName of [
    "Overview",
    "Forms",
    "Form Pairs",
    "Questions",
    "Role-qualified Questions",
    "Form Question Map",
  ]) {
    const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
    const safeName = sheetName.toLowerCase().replaceAll(" ", "-");
    await fs.writeFile(
      path.join(OUTPUT_DIR, `${safeName}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const inspection = await workbook.inspect({
    kind: "workbook,sheet,table,formula",
    maxChars: 12000,
    tableMaxRows: 4,
    tableMaxCols: 6,
    options: { maxResults: 100 },
  });
  await fs.writeFile(path.join(OUTPUT_DIR, "inspection.ndjson"), inspection.ndjson, "utf8");
  const formulaErrors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  await fs.writeFile(
    path.join(OUTPUT_DIR, "formula-errors.ndjson"),
    formulaErrors.ndjson,
    "utf8",
  );
}

await main();
