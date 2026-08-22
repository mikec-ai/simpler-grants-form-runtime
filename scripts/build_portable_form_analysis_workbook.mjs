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

async function csvRows(filename, labels) {
  const parsed = parseCsv(await fs.readFile(path.join(ANALYSIS_DIR, filename), "utf8"));
  const headers = parsed[0];
  return [
    labels,
    ...parsed.slice(1).map((row) => row.map((value, index) => typed(value ?? headers[index]))),
  ];
}

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
    "Form Key",
    "Form Name",
    "Version",
    "Semantic Question Occurrences",
    "Content Capture Mechanisms",
    "Semantic Mapping Status",
    "Published Coverage Eligible",
    "Production Ready",
  ]);
  const pairs = await csvRows("form-pairs.csv", [
    "Form A",
    "Form B",
    "Proposed Similarity",
    "Questions in Common",
    "Unique Questions Across Pair",
    "% of Form A Shared by Form B",
    "% of Form B Shared by Form A",
    "Accepted Similarity",
    "Accepted Questions in Common",
  ]);
  const questions = await csvRows("questions.csv", [
    "Question ID",
    "Question",
    "Validation Variants",
    "Forms with Proposed Use",
    "Forms with Accepted Use",
    "Forms with Published Use",
  ]);
  const associations = await csvRows("form-question-map.csv", [
    "Form Key",
    "Question ID",
    "Schema ID",
    "Analysis Classification",
    "Role",
    "Path in Form Schema",
    "Mapping Status",
    "Included in Proposed Overlap",
    "Included in Accepted Overlap",
    "Path in Grants.gov XML",
    "XML Type Source",
    "XML Type",
    "XSD Source Link",
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
    [38, 38, 17, 18, 23, 23, 23, 17, 22],
    [2, 5, 6, 7],
  );
  addDataSheet(workbook, "Questions", questions, "QuestionsTable", [64, 52, 19, 23, 22, 22]);
  addDataSheet(
    workbook,
    "Form Question Map",
    associations,
    "FormQuestionMapTable",
    [24, 48, 52, 25, 25, 58, 20, 23, 23, 58, 48, 24, 62],
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
    ["Unique semantic questions proposed", "=COUNTA(Questions!A2:A500)"],
    ["Form to question associations", '=COUNTIF(\'Form Question Map\'!D2:D1000,"semantic_question")'],
    ["Attachment capture mechanisms", '=COUNTIF(\'Form Question Map\'!D2:D1000,"content_capture_mechanism")'],
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
    ["Form Pairs", "Proposed question overlap for every pair of forms. Similarity is common questions divided by unique questions across both forms.", null, null, null, null, null, null],
    ["Questions", "The portable semantic question catalog and the number of forms in which each question is proposed to appear.", null, null, null, null, null, null],
    ["Form Question Map", "The association table connecting each form occurrence to a semantic question or an attachment capture mechanism, including XML metadata when available.", null, null, null, null, null, null],
    ["Proposed", "Agent-supported reuse evidence that still requires semantic review. Proposed values do not contribute to accepted or published coverage.", null, null, null, null, null, null],
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

  const sortedPairs = pairs.slice(1).sort((left, right) => right[2] - left[2]).slice(0, 8);
  overview.getRange("A18:C26").values = [
    ["Form Pair", "Proposed Similarity", "Questions in Common"],
    ...sortedPairs.map((row) => [`${row[0]} + ${row[1]}`, row[2], row[3]]),
  ];
  overview.getRange("A18:C18").format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white },
  };
  overview.getRange("B19:B26").format.numberFormat = "0.0%";
  overview.getRange("J18:K26").values = [
    ["Form Pair", "Questions in Common"],
    ...sortedPairs.map((row) => [`${row[0]} + ${row[1]}`, row[3]]),
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

  for (const sheetName of ["Overview", "Forms", "Form Pairs", "Questions", "Form Question Map"]) {
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
}

await main();
