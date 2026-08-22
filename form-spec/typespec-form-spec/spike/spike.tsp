import "@typespec/json-schema";
import "@simpler-grants/form-spec";

using JsonSchema;
using SimplerForms;

@jsonSchema
namespace Spike;

enum CountryCode {
  usa: "USA: UNITED STATES",
  outsideUs: "Outside the US",
}

// ---- SPIKE 4: does a composed model property emit a $ref? ----
@Question.meta(#{ id: "generics/person-name" })
@Catalog.tag(TagName.person, TagName.name)
@UI.order(QuestionPersonName.prefix, QuestionPersonName.firstName, QuestionPersonName.lastName)
model QuestionPersonName {
  @UI.label("Prefix")
  @maxLength(10)
  prefix?: string;

  @UI.label("First Name")
  @maxLength(35)
  firstName: string;

  @UI.label("Last Name")
  @maxLength(60)
  lastName: string;
}

@Question.meta(#{ id: "generics/address" })
@Catalog.tag(TagName.address)
model QuestionAddress {
  @UI.label("Street 1")
  street1: string;

  @UI.label("Country")
  country: CountryCode;

  // ---- SPIKE 1: ModelProperty as a NON-TARGET param via member expression ----
  @UI.label("Province")
  @UI.visibleWhen(QuestionAddress.country, CountryCode.outsideUs)
  province?: string;

  @UI.label("State")
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.usa)
  state?: string;
}

@Question.meta(#{ id: "poc/details" })
@Catalog.entity(EntityName.poc)
model QuestionPocDetails {
  name: QuestionPersonName;
  address: QuestionAddress;

  @UI.label("Email")
  email: string;
}

// ---- SPIKE 2 + 3: section enum, member ref, and member ref inside a literal ----
enum SpikeSection {
  /** Contacts for this application. */
  contacts: "1. Contacts",

  orgUnit: "1a. Organizational Unit",
}

@Form.meta(#{
  id: "spike-form",
  formId: "00000000-0000-0000-0000-000000000000",
  formName: "SPIKE",
  shortFormName: "Spike",
  formVersion: "1.0",
})
@UI.sections(SpikeSection)
model SpikeForm {
  @UI.section(SpikeSection.contacts)
  @UI.overrides(#{
    `address.street1`: #{ label: "8d. Street1", widget: WidgetName.Text },
    `email`: #{ label: "Primary Email", section: SpikeSection.orgUnit },
  })
  contact: QuestionPocDetails;

  @UI.section(SpikeSection.contacts)
  @Sgg.prePopulate(SggPrePop.agencyName)
  agencyName?: string;

  @UI.section(SpikeSection.contacts)
  @UI.readOnly
  @Validation.computed(Op.Sum, SpikeForm.agencyName, SpikeForm.total)
  total?: string;
}
