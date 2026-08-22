import "@simpler-grants/form-spec";
import "./index.tsp";
import "../question-bank/aor/index.tsp";
import "../question-bank/application/index.tsp";
import "../question-bank/generics/index.tsp";
import "../question-bank/opportunity/index.tsp";
import "../question-bank/poc/index.tsp";
import "../question-bank/primary-org/index.tsp";
import "../question-bank/project/index.tsp";

using SimplerForms;
using QuestionBank.Aor;
using QuestionBank.Application;
using QuestionBank.Generics;
using QuestionBank.Opportunity;
using QuestionBank.Poc;
using QuestionBank.PrimaryOrg;
using QuestionBank.Project;

namespace Forms.SF424Short;

/** The numbered boxes of the paper form, in order. */
enum Sf424ShortSection {
  federalAgency: "1. Name of Federal Agency",
  assistanceListing: "2. Assistance Listing Number and Title",
  dateReceived: "3. Date Received",
  fundingOpportunity: "4. Funding Opportunity Number and Title",
  applicantInformation: "5. Applicant Information",
  projectInformation: "6. Project Information",
  projectDirector: "7. Project Director",
  contactPerson: "8. Primary Contact/Grants Administrator",
  authorizedRepresentative: "9. Authorized Representative",
}

// Boxes 7 and 8 ask for the same thing about two different people, so this form composes one
// question twice. It orders the members its own way -- contact details before the address,
// where Key Contacts puts the address first -- and requires the title, which the question
// leaves optional. Both are form deltas; neither forks the question.
/** A person to contact about this application. */
@UI.label("Contact")
@UI.order(
  Sf424ShortContact.name,
  Sf424ShortContact.title,
  Sf424ShortContact.email,
  Sf424ShortContact.phone,
  Sf424ShortContact.fax,
  Sf424ShortContact.address
)
model Sf424ShortContact extends QuestionPocDetails {
  /** Enter the position title. */
  @UI.label("Title")
  title: ContactTitle;
}

/** Application for Federal Domestic Assistance-Short Organizational (SF-424) */
@Form.meta(#{
  id: "sf424-short",
  formId: "cf355a4d-d840-43fd-a78f-729edf41ab4c",
  legacyFormId: 711,
  formName: "Application for Federal Domestic Assistance-Short Organizational (SF-424)",
  shortFormName: "SF424_Short_3_0",
  formVersion: "3.0",
  agencyCode: "SGG",
  ombNumber: "4040-0003",
  formType: "SF424_SHORT",
  sggVersion: "1.0",
})
@UI.sections(Sf424ShortSection)
// Box 9's certification is long, and the paper form prints it in full beneath the checkbox.
@UI.overrides(#{ `applicationCertification`: #{ printDescription: true } })
@Sgg.prePopulate(#{
  `agencyName`: SggPrePop.agencyName,
  `assistanceListingNumber`: SggPrePop.assistanceListingNumber,
  `assistanceListingProgramTitle`: SggPrePop.assistanceListingProgramTitle,
  `fundingOpportunityNumber`: SggPrePop.opportunityNumber,
  `fundingOpportunityTitle`: SggPrePop.opportunityTitle,
  `samUei`: SggPrePop.uei,
})
model SF424Short {
  /** Pre-populated from the Application cover sheet. */
  @UI.label("Name of Federal Agency")
  @UI.section(Sf424ShortSection.federalAgency)
  @UI.readOnly
  agencyName: AgencyName;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Assistance Listing Number")
  @UI.section(Sf424ShortSection.assistanceListing)
  @UI.readOnly
  assistanceListingNumber?: AssistanceListingNumber;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Assistance Listing Title")
  @UI.section(Sf424ShortSection.assistanceListing)
  @UI.readOnly
  assistanceListingProgramTitle?: AssistanceListingTitle;

  /** Completed by Grants.gov upon submission. */
  @UI.label("Date Received")
  @UI.section(Sf424ShortSection.dateReceived)
  @UI.readOnly
  dateReceived?: DateReceived;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Funding Opportunity Number")
  @UI.section(Sf424ShortSection.fundingOpportunity)
  @UI.readOnly
  fundingOpportunityNumber: OpportunityNumber;

  /** Pre-populated from the Application cover sheet. */
  @UI.label("Funding Opportunity Title")
  @UI.section(Sf424ShortSection.fundingOpportunity)
  @UI.readOnly
  fundingOpportunityTitle: OpportunityTitle;

  /** Enter the legal name of applicant that will undertake the assistance activity. This is the name that the organization has registered with the System for Award Management (SAM.gov). Information on registering with SAM may be obtained by visiting the Grants.gov website. */
  @UI.label("Legal Name")
  @UI.section(Sf424ShortSection.applicantInformation)
  organizationName: LegalName;

  /** Enter the address of the applicant. */
  @UI.label("Address")
  @UI.section(Sf424ShortSection.applicantInformation)
  applicant: QuestionPrimaryOrgAddress;

  /** Enter the applicant's web address, if applicable. */
  @UI.label("Web Address")
  @UI.section(Sf424ShortSection.applicantInformation)
  @minLength(1)
  @maxLength(250)
  applicantWebAddress?: string;

  /** Select a minimum of one applicant type or select up to three applicant types in accordance with agency instructions. If “Other” is selected, then specify Other Type of Applicant in text box. */
  @UI.label("Type of Applicant")
  @UI.section(Sf424ShortSection.applicantInformation)
  @UI.widget(WidgetName.MultiSelect)
  applicantTypeCode: ApplicantTypes;

  /** Enter the applicant type here if you selected "Other (specify)" for Type of applicant. */
  @UI.label("Type of Applicant Other Explanation")
  @UI.section(Sf424ShortSection.applicantInformation)
  @Validation.requiredWhen(SF424Short.applicantTypeCode, ApplicantTypeCode.X)
  applicantTypeOtherSpecify?: ApplicantTypeOther;

  /** Enter either TIN or EIN as assigned by the Internal Revenue Service.  If your organization is not in the US, enter 44-4444444. */
  @UI.label("EIN/TIN")
  @UI.section(Sf424ShortSection.applicantInformation)
  employerTaxpayerIdentificationNumber: EmployerIdentificationNumber;

  /** UEI of the applicant organization. This field is pre-populated from the Application cover sheet. */
  @UI.label("SAM UEI")
  @UI.section(Sf424ShortSection.applicantInformation)
  @UI.readOnly
  samUei: SamUei;

  /** Congressional District of Applicant is required: Enter the Congressional District in the format: 2 character State Abbreviation - 3 character District Number. Examples: CA-005 for California's 5th District, CA-012 for California's 12th District, NC-103 for North Carolina's 103rd District. If outside the U.S., enter 00-000. */
  @UI.label("Congressional District of Applicant")
  @UI.section(Sf424ShortSection.applicantInformation)
  congressionalDistrictApplicant: CongressionalDistrict;

  /** Enter a brief, descriptive title of the project. */
  @UI.label("Project Title")
  @UI.section(Sf424ShortSection.projectInformation)
  projectTitle: ProjectTitle;

  /** Enter a brief description of the project. */
  @UI.label("Project Description")
  @UI.section(Sf424ShortSection.projectInformation)
  @minLength(1)
  @maxLength(1000)
  projectDescription: string;

  /** Enter the date in the format MM/DD/YYYY. */
  @UI.label("Project Start Date")
  @UI.section(Sf424ShortSection.projectInformation)
  projectStartDate: ProjectStartDate;

  /** Enter the date in the format MM/DD/YYYY. */
  @UI.label("Project End Date")
  @UI.section(Sf424ShortSection.projectInformation)
  projectEndDate: ProjectEndDate;

  @UI.label("Project Director")
  @UI.section(Sf424ShortSection.projectDirector)
  projectDirector: Sf424ShortContact;

  @UI.label("Same as Project Director (if checked, fill in information same as Project Director above)")
  @UI.section(Sf424ShortSection.contactPerson)
  sameAsProjectDirector?: boolean;

  @UI.label("Primary Contact/Grants Administrator")
  @UI.section(Sf424ShortSection.contactPerson)
  contactPerson: Sf424ShortContact;

  /** ** The list of certifications and assurances, or an internet site where you may obtain this list, is contained in the announcement or agency specific instructions. By signing this application, I certify (1) to the statements contained in the list of certifications and (2) that the statements herein are true, complete and accurate to the best of my knowledge. I also provide the required assurances and agree to comply with any resulting terms if I accept an award. I am aware that any false, fictitious, or fraudulent statements or claims may subject me to criminal, civil, or administrative penalties. (U.S. Code, Title 18, Section 1001) */
  @UI.label("** I Agree")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  applicationCertification: boolean;

  /** Enter the name of the authorized representative. */
  @UI.label("Authorized Representative")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  authorizedRepresentative: QuestionAorName;

  /** Enter the position title. */
  @UI.label("Title")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  authorizedRepresentativeTitle: AorTitle;

  /** Enter a valid email Address. */
  @UI.label("Email")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  authorizedRepresentativeEmail: AorEmail;

  /** Enter the daytime Telephone Number. */
  @UI.label("Telephone Number")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  authorizedRepresentativePhoneNumber: AorPhone;

  /** Enter the Fax Number. */
  @UI.label("Fax Number")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  authorizedRepresentativeFax?: AorFax;

  /** Completed by Grants.gov upon submission. */
  @UI.label("Signature of Authorized Representative")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  @UI.readOnly
  aorSignature?: AorSignature;

  /** Completed by Grants.gov upon submission. */
  @UI.label("Date Signed")
  @UI.section(Sf424ShortSection.authorizedRepresentative)
  @UI.readOnly
  authorizedRepresentativeDateSigned?: AorDateSigned;
}
