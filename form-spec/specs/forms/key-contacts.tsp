import "@simpler-grants/form-spec";
import "./index.tsp";
import "../question-bank/generics/index.tsp";
import "../question-bank/poc/index.tsp";

using SimplerForms;
using QuestionBank.Generics;
using QuestionBank.Poc;

namespace Forms.KeyContacts;

/** Sections, in paper-form order. */
enum KeyContactsSection {
  /** Enter between 1 and 4 key contacts and their role on the project. */
  keyContacts: "Key Contacts",
}

/** One key contact and their role on the project. */
@UI.label("Key Contact")
@UI.order(
  KeyContactPerson.projectRole,
  KeyContactPerson.name,
  KeyContactPerson.title,
  KeyContactPerson.organizationalAffiliation,
  KeyContactPerson.address,
  KeyContactPerson.phone,
  KeyContactPerson.fax,
  KeyContactPerson.email
)
model KeyContactPerson extends QuestionPocDetails {
  /** Enter the individual's role on the project (e.g., project manager, fiscal contact). */
  @UI.label("Project Role")
  @minLength(1)
  @maxLength(45)
  projectRole: string;

  /** Enter the contact's organizational affiliation. */
  @UI.label("Organizational Affiliation")
  organizationalAffiliation?: OrganizationName;
}

/** KEY CONTACTS (Grants.gov FID 683, v2.0) */
@Form.meta(#{
  id: "key-contacts",
  formId: "f140c7db-724d-4954-bebd-081c0527908c",
  legacyFormId: 683,
  formName: "KEY CONTACTS",
  shortFormName: "Key_Contacts",
  formVersion: "2.0",
  agencyCode: "SGG",
  ombNumber: "4040-0010",
  formType: "KEY_CONTACTS",
  sggVersion: "1.0",
})
@UI.sections(KeyContactsSection)
model KeyContacts {
  /** Enter the legal name of the applicant that will undertake the assistance activity. This field is required. */
  @UI.label("Applicant Organization Name")
  @UI.section(KeyContactsSection.keyContacts)
  applicantOrganizationName: OrganizationName;

  /** Enter between 1 and 4 key contacts and their role on the project. */
  @UI.label("Key Contacts")
  @UI.helpText("You may enter up to four (4) Key Contacts. At least 1 (one) contact person is required. Additional contacts are optional.")
  @UI.section(KeyContactsSection.keyContacts)
  @minItems(1)
  @maxItems(4)
  keyContacts: KeyContactPerson[];
}
