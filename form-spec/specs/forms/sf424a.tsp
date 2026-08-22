import "@simpler-grants/form-spec";
import "./index.tsp";
import "../question-bank/budget/index.tsp";
import "../question-bank/opportunity/index.tsp";

using SimplerForms;
using QuestionBank.Budget;

namespace Forms.SF424a;

/** The lettered sections of the paper form. */
enum Sf424aSection {
  SectionA: "Section A - Budget summary",

  /** Enter funds required for each object class category for the selected program. */
  SectionB: "Section B - Budget categories",

  /** Enter resources provided by the applicant, state, or other sources (e.g., donors) for the selected program. */
  SectionC: "Section C - Non-federal resources",

  SectionD: "Section D - Forecasted cash needs",
  SectionE: "Section E - Budget estimates of federal funds needed for balance of the project ",
  SectionF: "Section F - Other budget information",
}

// The four budget questions are asked once per activity here and once more as a total at
// the form's root. That is the whole shape of SF-424A: four questions, asked twice.
model ActivityLineItem {
  @minLength(0)
  @maxLength(120)
  activityTitle: string;

  @minLength(0)
  @maxLength(15)
  assistanceListingNumber?: string;

  budgetSummary?: QuestionBudgetSummary;
  budgetCategories?: QuestionBudgetCategories;
  nonFederalResources?: QuestionNonFederalResources;
  federalFundEstimates?: QuestionFederalFundEstimates;
}

// Cash needs for the first year, split into the federal and non-federal shares.
model ForecastedCashNeeds {
  federalForecastedCashNeeds?: QuestionForecastedCashNeeds;
  nonFederalForecastedCashNeeds?: QuestionForecastedCashNeeds;

  @Validation.totals(
    ForecastedCashNeeds.federalForecastedCashNeeds,
    ForecastedCashNeeds.nonFederalForecastedCashNeeds
  )
  totalForecastedCashNeeds?: QuestionForecastedCashNeeds;
}

/** Budget Information for Non-Construction Programs (SF-424A) */
@Form.meta(#{
  id: "sf424a",
  formId: "08e6603f-d197-4a60-98cd-d49acb1fc1fd",
  legacyFormId: 241,
  formName: "Budget Information for Non-Construction Programs (SF-424A)",
  shortFormName: "SF424A",
  formVersion: "1.0",
  agencyCode: "SGG",
  ombNumber: "4040-0006",
  formType: "SF424A",
  sggVersion: "1.0",
})
@UI.sections(Sf424aSection)
// Each section is one purpose-built SGG component that lays out its own table, so the
// section receives a property list rather than a field list.
@Sgg.multiField(Sf424aSection.SectionA, WidgetName.Budget424aSectionA)
@Sgg.multiField(Sf424aSection.SectionB, WidgetName.Budget424aSectionB)
@Sgg.multiField(Sf424aSection.SectionC, WidgetName.Budget424aSectionC)
@Sgg.multiField(Sf424aSection.SectionD, WidgetName.Budget424aSectionD)
@Sgg.multiField(Sf424aSection.SectionE, WidgetName.Budget424aSectionE)
@Sgg.multiField(Sf424aSection.SectionF, WidgetName.Budget424aSectionF)
model SF424a {
  @UI.section(Sf424aSection.SectionA)
  @minItems(1)
  @maxItems(4)
  activityLineItems: ActivityLineItem[];

  @UI.section(Sf424aSection.SectionA)
  @Validation.totals(SF424a.activityLineItems)
  totalBudgetSummary?: QuestionBudgetSummary;

  @UI.section(Sf424aSection.SectionB)
  @Validation.totals(SF424a.activityLineItems)
  totalBudgetCategories?: QuestionBudgetCategories;

  @UI.section(Sf424aSection.SectionC)
  @Validation.totals(SF424a.activityLineItems)
  totalNonFederalResources?: QuestionNonFederalResources;

  @UI.section(Sf424aSection.SectionD)
  forecastedCashNeeds?: ForecastedCashNeeds;

  @UI.section(Sf424aSection.SectionE)
  @Validation.totals(SF424a.activityLineItems)
  totalFederalFundEstimates?: QuestionFederalFundEstimates;

  /** Use this space to explain amounts for individual direct object class cost categories that may appear to be out of the ordinary or to explain the details as required by the Federal grantor agency. */
  @UI.label("Direct Charges")
  @UI.section(Sf424aSection.SectionF)
  @minLength(0)
  @maxLength(50)
  directChargesExplanation?: string;

  /** Enter the type of indirect rate (provisional, predetermined, final or fixed) that will be in effect during the funding period, the estimated amount of the base to which the rate is applied, and the total indirect expense. */
  @UI.label("Indirect Charges")
  @UI.section(Sf424aSection.SectionF)
  @minLength(0)
  @maxLength(50)
  indirectChargesExplanation?: string;

  /** Provide any other explanations or comments deemed necessary. */
  @UI.label("Remarks")
  @UI.section(Sf424aSection.SectionF)
  @minLength(0)
  @maxLength(250)
  remarks?: string;

  /** Is this form complete? */
  @UI.label("Confirmation")
  @UI.section(Sf424aSection.SectionF)
  confirmation: true;
}
