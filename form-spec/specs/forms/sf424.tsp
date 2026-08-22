import "@simpler-grants/form-spec";
import "./index.tsp";
import "../question-bank/generics/index.tsp";
import "../question-bank/opportunity/index.tsp";
import "../question-bank/primary-org/index.tsp";
import "../question-bank/project/index.tsp";

using SimplerForms;
using QuestionBank.Generics;
using QuestionBank.Opportunity;
using QuestionBank.PrimaryOrg;
using QuestionBank.Project;

namespace Forms.SF424;

/** The numbered boxes of the paper form, in order. */
enum Sf424Section {
  submissionType: "1. Type of Submission",
  applicationTypeAndRevision: "2. Type of Application",
  dateReceived: "3. Date Received",
  applicantIdentifier: "4. Applicant Identifier",
  federalIdentifiers: "5a. Federal Identifiers",
  federalAward: "5b. Federal Award",
  dateReceivedByState: "6. Date Received by State",
  stateApplicationIdentifier: "7. State Application Identifier",
  applicantInformation: "8. Applicant Information",
  organizationalUnit: "8e. Organizational Unit",
  contactPerson: "8f. Name and contact information of person to be contacted on matters involving this application",
  typeOfApplicant: "9. Type of Applicant",
  federalAgency: "10. Name of Federal Agency",
  assistanceListing: "11. Assistance Listing Number/Title",
  fundingOpportunity: "12. Funding Opportunity Number/Title",
  competitionIdentification: "13. Competition Identification Number/Title",
  areasAffected: "14. Areas Affected by Project",
  projectTitle: "15. Descriptive Title of Applicant's Project",
  congressionalDistricts: "16. Congressional Districts",
  projectDates: "17. Proposed Project Start and End Dates",
  estimatedFunding: "18. Estimated Funding",
  stateReview: "19. Is Application Subject to Review by State Under Executive Order?",
  federalDebt: "20. Is the Applicant Delinquent on any Federal Debt?",
  authorizedRepresentative: "21. Authorized Representative",
}

/** Select one type of submission in accordance with agency instructions. */
enum SubmissionType {
  preapplication: "Preapplication",
  application: "Application",
  changedCorrected: "Changed/Corrected Application",
}

/** Select one type of application in accordance with agency instructions. */
enum ApplicationType {
  new: "New",
  continuation: "Continuation",
  revision: "Revision",
}

/** The kind of change a revision makes to an existing award. */
enum RevisionType {
  A: "A: Increase Award",
  B: "B: Decrease Award",
  C: "C: Increase Duration",
  D: "D: Decrease Duration",
  E: "E: Other (specify)",
  AC: "AC: Increase Award, Increase Duration",
  AD: "AD: Increase Award, Decrease Duration",
  BC: "BC: Decrease Award, Increase Duration",
  BD: "BD: Decrease Award, Decrease Duration",
}

/** The applicant's category, from the Executive Order 12372 list. */
enum ApplicantType {
  A: "A: State Government",
  B: "B: County Government",
  C: "C: City or Township Government",
  D: "D: Special District Government",
  E: "E: Regional Organization",
  F: "F: U.S. Territory or Possession",
  G: "G: Independent School District",
  H: "H: Public/state Controlled Institution of Higher Education",
  I: "I: Indian/Native American Tribal Government (Federally Recognized)",
  J: "J: Indian/Native American Tribal Government (Other than Federally Recognized)",
  K: "K: Indian/Native American Tribally Designated Organization",
  L: "L: Public/Indian Housing Authority",
  M: "M: Nonprofit with 501C3 IRS Status (Other than Institution of Higher Education)",
  N: "N: Nonprofit without 501C3 IRS Status (Other than Institution of Higher Education)",
  O: "O: Private Institution of Higher Education",
  P: "P: Individual",
  Q: "Q: For-Profit Organization (Other than Small Business)",
  R: "R: Small Business",
  S: "S: Hispanic-serving Institution",
  T: "T: Historically Black Colleges and Universities (HBCUs)",
  U: "U: Tribally Controlled Colleges and Universities (TCCUs)",
  V: "V: Alaska Native and Native Hawaiian Serving Institutions",
  W: "W: Non-domestic (non-US) Entity",
  X: "X: Other (specify)",
}

/** Whether Executive Order 12372 review applies, and if so what happened. */
enum StateReview {
  madeAvailable: "a. This application was made available to the state under the Executive Order 12372 Process for review on",
  notSelected: "b. Program is subject to E.O. 12372 but has not been selected by the state for review.",
  notCovered: "c. Program is not covered by E.O. 12372.",
}

/** APPLICATION FOR FEDERAL ASSISTANCE (SF-424) */
@Form.meta(#{
  id: "sf424",
  formId: "1623b310-85be-496a-b84b-34bdee22a68a",
  legacyFormId: 713,
  formName: "Application for Federal Assistance (SF-424)",
  shortFormName: "SF424_4_0",
  formVersion: "4.0",
  agencyCode: "SGG",
  ombNumber: "4040-0004",
  formType: "SF424",
  sggVersion: "1.0",
})
@UI.sections(Sf424Section)
// Box 8d asks for the applicant's address but not its county, which every other form
// using this question does ask for. A form-scoped override, so the question stays one
// question.
@UI.overrides(#{ `applicant.county`: #{ omit: true } })
model SF424 {
  /** Select one type of submission in accordance with agency instructions. */
  @UI.label("Submission Type")
  @UI.section(Sf424Section.submissionType)
  submissionType: SubmissionType;

  /** Select one type of application in accordance with agency instructions. */
  @UI.label("Application Type")
  @UI.section(Sf424Section.applicationTypeAndRevision)
  applicationType: ApplicationType;

  /** Select a revision type from the list provided. A selection is required if Type of Application is Revision. */
  @UI.label("Revision Type")
  @UI.section(Sf424Section.applicationTypeAndRevision)
  @Validation.requiredWhen(SF424.applicationType, ApplicationType.revision)
  revisionType?: RevisionType;

  /** Please specify the type of revision. This field is required if E. Other is checked. */
  @UI.label("Other Explanation")
  @UI.section(Sf424Section.applicationTypeAndRevision)
  @Validation.requiredWhen(SF424.revisionType, RevisionType.E)
  revisionOtherSpecify?: string;

  /** Completed by Grants.gov upon submission. */
  @UI.label("Date Received")
  @UI.section(Sf424Section.dateReceived)
  @UI.readOnly
  dateReceived?: SubmittedDate;

  /** Enter the applicant's control number, if applicable. */
  @UI.label("Applicant Identifier")
  @UI.section(Sf424Section.applicantIdentifier)
  @minLength(1)
  @maxLength(30)
  applicantId?: string;

  /** Enter the number assigned to your organization by the Federal agency. */
  @UI.label("Federal Entity Identifier")
  @UI.section(Sf424Section.federalIdentifiers)
  @minLength(1)
  @maxLength(30)
  federalEntityIdentifier?: string;

  /** For new applications leave blank. For a continuation or revision to an existing award, enter the previously assigned Federal award identifier number. If a changed/corrected application, enter the Federal Identifier in accordance with agency instructions. */
  @UI.label("Federal Award Identifier")
  @UI.section(Sf424Section.federalAward)
  @minLength(1)
  @maxLength(25)
  @Validation.requiredWhen(SF424.applicationType, ApplicationType.revision)
  @Validation.requiredWhen(SF424.applicationType, ApplicationType.continuation)
  federalAwardIdentifier?: string;

  /** Leave blank, to be filled out by state. */
  @UI.label("Date Received By State")
  @UI.section(Sf424Section.dateReceivedByState)
  @UI.readOnly
  stateReceiveDate?: plainDate;

  /** Leave blank, to be filled out by state. */
  @UI.label("State Application Identifier")
  @UI.section(Sf424Section.stateApplicationIdentifier)
  @UI.readOnly
  @minLength(0)
  @maxLength(30)
  stateApplicationId?: string;

  /** Enter the legal name of the applicant that will undertake the assistance activity. This is the organization that has registered with the System for Award Management (SAM). Information on registering with SAM may be obtained by visiting SAM.gov. */
  @UI.label("Legal Name")
  @UI.section(Sf424Section.applicantInformation)
  organizationName: OrganizationName;

  /** Enter either TIN or EIN as assigned by the Internal Revenue Service.  If your organization is not in the US, enter 44-4444444. */
  @UI.label("EIN/TIN")
  @UI.section(Sf424Section.applicantInformation)
  employerTaxpayerIdentificationNumber: EmployerIdentificationNumber;

  /** UEI of the applicant organization. This field is pre-populated from the Application cover sheet. */
  @UI.label("SAM UEI")
  @UI.section(Sf424Section.applicantInformation)
  @Sgg.prePopulate(SggPrePop.uei)
  samUei: SamUei;

  /** Enter information about the applicant. */
  @UI.label("Applicant")
  @UI.section(Sf424Section.applicantInformation)
  applicant: QuestionAddress;

  /** Enter the name of primary organizational department, service, laboratory, or equivalent level within the organization which will undertake the assistance activity. */
  @UI.label("Department Name")
  @UI.section(Sf424Section.organizationalUnit)
  @minLength(1)
  @maxLength(30)
  departmentName?: string;

  /** Enter the name of primary organizational division, office, or major subdivision which will undertake the assistance activity. */
  @UI.label("Division Name")
  @UI.section(Sf424Section.organizationalUnit)
  @minLength(1)
  @maxLength(100)
  divisionName?: string;

  /** Enter information about the contact person. */
  @UI.label("Contact Person")
  @UI.section(Sf424Section.contactPerson)
  contactPerson: QuestionPersonName;

  /** Enter the position title. */
  @UI.label("Title")
  @UI.section(Sf424Section.contactPerson)
  contactPersonTitle?: ContactTitle;

  /** Enter the organization if different from the applicant organization. */
  @UI.label("Organizational Affiliation")
  @UI.section(Sf424Section.contactPerson)
  @minLength(1)
  @maxLength(60)
  organizationAffiliation?: string;

  /** Enter the daytime Telephone Number. */
  @UI.label("Telephone Number")
  @UI.section(Sf424Section.contactPerson)
  phoneNumber: PhoneNumber;

  /** Enter the fax Number. */
  @UI.label("Fax Number")
  @UI.section(Sf424Section.contactPerson)
  fax?: PhoneNumber;

  /** Enter a valid email Address. */
  @UI.label("Email")
  @UI.section(Sf424Section.contactPerson)
  email: EmailAddress;

  /** Select the appropriate applicant types. */
  @UI.label("Type of Applicant")
  @UI.section(Sf424Section.typeOfApplicant)
  @minItems(1)
  @maxItems(3)
  applicantTypeCode: ApplicantType[];

  /** Enter the applicant type here if you selected "Other (specify)" for Type of applicant. */
  @UI.label("Type of Applicant Other Explanation")
  @UI.section(Sf424Section.typeOfApplicant)
  @minLength(0)
  @maxLength(30)
  @Validation.requiredWhen(SF424.applicantTypeCode, ApplicantType.X)
  applicantTypeOtherSpecify?: string;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Agency Name")
  @UI.section(Sf424Section.federalAgency)
  @Sgg.prePopulate(SggPrePop.agencyName)
  agencyName: AgencyName;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Assistance Listing Number")
  @UI.section(Sf424Section.assistanceListing)
  @Sgg.prePopulate(SggPrePop.assistanceListingNumber)
  assistanceListingNumber?: AssistanceListingNumber;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Assistance Listing Title")
  @UI.section(Sf424Section.assistanceListing)
  @Sgg.prePopulate(SggPrePop.assistanceListingProgramTitle)
  assistanceListingProgramTitle?: AssistanceListingTitle;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Opportunity Number")
  @UI.section(Sf424Section.fundingOpportunity)
  @Sgg.prePopulate(SggPrePop.opportunityNumber)
  fundingOpportunityNumber: OpportunityNumber;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Opportunity title")
  @UI.section(Sf424Section.fundingOpportunity)
  @Sgg.prePopulate(SggPrePop.opportunityTitle)
  fundingOpportunityTitle: OpportunityTitle;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Competition Number")
  @UI.section(Sf424Section.competitionIdentification)
  @Sgg.prePopulate(SggPrePop.publicCompetitionId)
  competitionIdentificationNumber?: CompetitionNumber;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Competition Title")
  @UI.section(Sf424Section.competitionIdentification)
  @Sgg.prePopulate(SggPrePop.competitionTitle)
  competitionIdentificationTitle?: CompetitionTitle;

  /** List the areas or entities using the categories (e.g., cities, counties, states, etc.) specified in agency instructions. */
  @UI.label("Areas Affected")
  @UI.section(Sf424Section.areasAffected)
  @UI.widget(WidgetName.Attachment)
  areasAffected?: AttachmentRef;

  /** Enter a brief, descriptive title of the project. */
  @UI.label("Project Title")
  @UI.section(Sf424Section.projectTitle)
  projectTitle: ProjectTitle;

  /** Attach file(s) using the appropriate buttons. */
  @UI.label("Additional Project Title")
  @UI.section(Sf424Section.projectTitle)
  @UI.widget(WidgetName.AttachmentArray)
  @maxItems(100)
  additionalProjectTitle?: AttachmentRef[];

  /** Enter the Congressional District in the format: 2 character state Abbreviation - 3 character District Number. Examples: CA-005 for California's 5th district, CA-012 for California's 12th district.If outside the US, enter 00-000. */
  @UI.label("Applicant District")
  @UI.section(Sf424Section.congressionalDistricts)
  congressionalDistrictApplicant: CongressionalDistrict;

  /** Enter the Congressional District in the format: 2 character state Abbreviation - 3 character District Number. Examples: CA-005 for California's 5th district, CA-012 for California's 12th district.If all districts in a state are affected, enter "all" for the district number. Example: MD-all for all congressional districts in Maryland.If nationwide (all districts in all states), enter US-all.If the program/project is outside the US, enter 00-000. */
  @UI.label("Program District")
  @UI.section(Sf424Section.congressionalDistricts)
  congressionalDistrictProgramProject: CongressionalDistrict;

  /** Attach an additional list of Program/Project Congressional Districts if needed. */
  @UI.label("Additional Congressional Districts")
  @UI.section(Sf424Section.congressionalDistricts)
  @UI.widget(WidgetName.Attachment)
  additionalCongressionalDistricts?: AttachmentRef;

  /** Enter the date in the format MM/DD/YYYY.  */
  @UI.label("Project Start Date")
  @UI.section(Sf424Section.projectDates)
  projectStartDate: plainDate;

  /** Enter the date in the format MM/DD/YYYY.  */
  @UI.label("Project End Date")
  @UI.section(Sf424Section.projectDates)
  projectEndDate: plainDate;

  /** Enter the dollar amount. */
  @UI.label("Federal Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  federalEstimatedFunding: MonetaryAmount;

  /** Enter the dollar amount. */
  @UI.label("Applicant Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  applicantEstimatedFunding: MonetaryAmount;

  /** Enter the dollar amount. */
  @UI.label("State Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  stateEstimatedFunding: MonetaryAmount;

  /** Enter the dollar amount. */
  @UI.label("Local Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  localEstimatedFunding: MonetaryAmount;

  /** Enter the dollar amount. */
  @UI.label("Other Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  otherEstimatedFunding: MonetaryAmount;

  /** Enter the dollar amount. */
  @UI.label("Program Income Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  programIncomeEstimatedFunding: MonetaryAmount;

  /** This field is automatically calculated by Grants.gov */
  @UI.label("Total Estimated Funding")
  @UI.section(Sf424Section.estimatedFunding)
  @UI.readOnly
  @Validation.computed(
    Op.Sum,
    SF424.federalEstimatedFunding,
    SF424.applicantEstimatedFunding,
    SF424.stateEstimatedFunding,
    SF424.localEstimatedFunding,
    SF424.otherEstimatedFunding,
    SF424.programIncomeEstimatedFunding
  )
  totalEstimatedFunding: MonetaryAmount;

  /** One selection is required. */
  @UI.label("Is Application Subject to Review By State Under Executive Order 12372 Process?")
  @UI.section(Sf424Section.stateReview)
  stateReview: StateReview;

  /** If 'a' is selected, enter the date the application was submitted to the State. */
  @UI.label("State Review Date")
  @UI.section(Sf424Section.stateReview)
  @Validation.requiredWhen(SF424.stateReview, StateReview.madeAvailable)
  stateReviewAvailableDate?: plainDate;

  /** If 'Yes,' provide explanation in attachment. */
  @UI.label("Applicant Delinquent on Federal Debt")
  @UI.section(Sf424Section.federalDebt)
  @UI.widget(WidgetName.Radio)
  delinquentFederalDebt: boolean;

  @UI.label("Debt Explanation")
  @UI.section(Sf424Section.federalDebt)
  @UI.widget(WidgetName.Attachment)
  @Validation.requiredWhen(SF424.delinquentFederalDebt, true)
  debtExplanation?: AttachmentRef;

  /** By signing this application, I certify (1) to the statements contained in the list of certifications* and (2) that the statements herein are true, complete and accurate to the best of my knowledge. I also provide the required assurances** and agree to comply with any resulting terms if I accept an award. I am aware that any false, fictitious, or fraudulent statements or claims may subject me to criminal, civil, or administrative penalties. (U.S. Code, Title 18, Section 1001) */
  @UI.label("Certification Agree")
  @UI.section(Sf424Section.authorizedRepresentative)
  certificationAgree: boolean;

  @UI.label("Authorized Representative")
  @UI.section(Sf424Section.authorizedRepresentative)
  authorizedRepresentative: QuestionPersonName;

  /** Enter the position title. */
  @UI.label("Title")
  @UI.section(Sf424Section.authorizedRepresentative)
  authorizedRepresentativeTitle: ContactTitle;

  /** Enter the daytime Telephone Number. */
  @UI.label("AOR Telephone Number")
  @UI.section(Sf424Section.authorizedRepresentative)
  authorizedRepresentativePhoneNumber: PhoneNumber;

  /** Enter the fax Number. */
  @UI.label("AOR fax Number")
  @UI.section(Sf424Section.authorizedRepresentative)
  authorizedRepresentativeFax?: PhoneNumber;

  /** Enter a valid email Address. */
  @UI.label("AOR email")
  @UI.section(Sf424Section.authorizedRepresentative)
  authorizedRepresentativeEmail: EmailAddress;

  @UI.label("AOR Signature")
  @UI.section(Sf424Section.authorizedRepresentative)
  @UI.readOnly
  aorSignature?: Signature;

  @UI.label("Date Signed")
  @UI.section(Sf424Section.authorizedRepresentative)
  @UI.readOnly
  dateSigned?: SubmittedDate;
}
