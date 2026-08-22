import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generics/index.tsp";

using SimplerForms;
using QuestionBank.Generics;

/**
 * The five budget tables of SF-424A, each a question in its own right. Every one is asked
 * twice on that form -- once per activity and once as a total -- and the budget family
 * asks several of them again.
 *
 * Where a table's own arithmetic is intrinsic to it, it is declared here rather than on
 * the forms: a direct-charge subtotal is the sum of the object-class categories no matter
 * which form is asking.
 */
namespace QuestionBank.Budget;

/** Estimated unobligated and new or revised funds, federal and non-federal. */
@Question.meta(#{ id: "budget/summary" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.money)
@UI.label("Budget Summary")
model QuestionBudgetSummary {
  federalEstimatedUnobligatedAmount?: MonetaryAmount;
  nonFederalEstimatedUnobligatedAmount?: MonetaryAmount;
  federalNewOrRevisedAmount?: MonetaryAmount;
  nonFederalNewOrRevisedAmount?: MonetaryAmount;
  totalAmount?: MonetaryAmount;
}

/** Funds required for each object class category. */
@Question.meta(#{ id: "budget/categories" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.money)
@UI.label("Budget Categories")
model QuestionBudgetCategories {
  personnelAmount?: MonetaryAmount;
  fringeBenefitsAmount?: MonetaryAmount;
  travelAmount?: MonetaryAmount;
  equipmentAmount?: MonetaryAmount;
  suppliesAmount?: MonetaryAmount;
  contractualAmount?: MonetaryAmount;
  constructionAmount?: MonetaryAmount;
  otherAmount?: MonetaryAmount;

  @Validation.computed(
    Op.Sum,
    QuestionBudgetCategories.personnelAmount,
    QuestionBudgetCategories.fringeBenefitsAmount,
    QuestionBudgetCategories.travelAmount,
    QuestionBudgetCategories.equipmentAmount,
    QuestionBudgetCategories.suppliesAmount,
    QuestionBudgetCategories.contractualAmount,
    QuestionBudgetCategories.constructionAmount,
    QuestionBudgetCategories.otherAmount
  )
  totalDirectChargeAmount?: MonetaryAmount;

  totalIndirectChargeAmount?: MonetaryAmount;

  @Validation.computed(
    Op.Sum,
    QuestionBudgetCategories.totalDirectChargeAmount,
    QuestionBudgetCategories.totalIndirectChargeAmount
  )
  totalAmount?: MonetaryAmount;

  programIncomeAmount?: MonetaryAmount;
}

/** Resources provided by the applicant, the state, or other sources. */
@Question.meta(#{ id: "budget/non-federal-resources" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.money)
@UI.label("Non-federal Resources")
model QuestionNonFederalResources {
  @minLength(0)
  @maxLength(120)
  grantProgram?: string;

  applicantAmount?: MonetaryAmount;
  stateAmount?: MonetaryAmount;
  otherAmount?: MonetaryAmount;

  @Validation.computed(
    Op.Sum,
    QuestionNonFederalResources.applicantAmount,
    QuestionNonFederalResources.stateAmount,
    QuestionNonFederalResources.otherAmount
  )
  totalAmount?: MonetaryAmount;
}

/** Federal funds needed for the balance of the project, by year. */
@Question.meta(#{ id: "budget/federal-fund-estimates" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.money)
@UI.label("Federal Fund Estimates")
model QuestionFederalFundEstimates {
  @minLength(0)
  @maxLength(120)
  grantProgram?: string;

  firstYearAmount?: MonetaryAmount;
  secondYearAmount?: MonetaryAmount;
  thirdYearAmount?: MonetaryAmount;
  fourthYearAmount?: MonetaryAmount;
}

/** Cash needed by quarter for the first year. */
@Question.meta(#{ id: "budget/forecasted-cash-needs" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.money)
@UI.label("Forecasted Cash Needs")
model QuestionForecastedCashNeeds {
  firstQuarterAmount?: MonetaryAmount;
  secondQuarterAmount?: MonetaryAmount;
  thirdQuarterAmount?: MonetaryAmount;
  fourthQuarterAmount?: MonetaryAmount;

  @Validation.computed(
    Op.Sum,
    QuestionForecastedCashNeeds.firstQuarterAmount,
    QuestionForecastedCashNeeds.secondQuarterAmount,
    QuestionForecastedCashNeeds.thirdQuarterAmount,
    QuestionForecastedCashNeeds.fourthQuarterAmount
  )
  totalAmount?: MonetaryAmount;
}
