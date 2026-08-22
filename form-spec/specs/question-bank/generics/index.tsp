import "@simpler-grants/form-spec";
import "../index.tsp";

using SimplerForms;

namespace QuestionBank.Generics;

/** A person's name, in five parts. */
@Question.meta(#{ id: "generics/person-name" })
@Catalog.tag(TagName.person, TagName.name)
@UI.label("Name")
model QuestionPersonName {
  /** Enter the Prefix. */
  @UI.label("Prefix")
  @maxLength(10)
  prefix?: string;

  /** Enter the First Name. */
  @UI.label("First Name")
  @maxLength(35)
  firstName: string;

  /** Enter the Middle Name. */
  @UI.label("Middle Name")
  @maxLength(25)
  middleName?: string;

  /** Enter the Last Name. */
  @UI.label("Last Name")
  @maxLength(60)
  lastName: string;

  /** Enter the Suffix. */
  @UI.label("Suffix")
  @maxLength(10)
  suffix?: string;
}

/** US State or Territory Code */
enum StateCode {
  AL: "AL: Alabama",
  AK: "AK: Alaska",
  CA: "CA: California",
  DC: "DC: District of Columbia",
}

/** Country Code */
enum CountryCode {
  USA: "USA: UNITED STATES",
  CAN: "CAN: CANADA",
}

/** Enter an address. */
@Question.meta(#{ id: "generics/address" })
@Catalog.tag(TagName.address)
@UI.label("Address")
model QuestionAddress {
  /** Enter the first line of the Street Address. */
  @UI.label("Street 1")
  @maxLength(55)
  street1: string;

  /** Enter the second line of the Street Address. */
  @UI.label("Street 2")
  @maxLength(55)
  street2?: string;

  /** Enter the city. */
  @UI.label("City")
  @maxLength(35)
  city: string;

  /** Enter the County or Parish. */
  @UI.label("County/Parish")
  @maxLength(30)
  county?: string;

  /** Enter the state. */
  @UI.label("State")
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA)
  state?: StateCode;

  /** Enter the province. */
  @UI.label("Province")
  @maxLength(30)
  province?: string;

  /** Enter the country. */
  @UI.label("Country")
  country: CountryCode;

  /** Enter the nine-digit Postal Code (e.g., ZIP Code). This field is required if the Country is the United States. */
  @UI.label("Zip / Postal Code")
  @maxLength(30)
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA)
  zipCode?: string;
}

/** A telephone or fax number. */
@Question.meta(#{ id: "generics/phone" })
@Catalog.tag(TagName.phone)
scalar PhoneNumber extends string;

/** An email address. */
@Question.meta(#{ id: "generics/email" })
@Catalog.tag(TagName.email)
scalar EmailAddress extends string;

/** Enter the legal name of the organization. */
@Question.meta(#{ id: "generics/organization-name" })
@Catalog.tag(TagName.organization, TagName.name)
@UI.label("Organization Name")
scalar OrganizationName extends string;

/** Enter the position title. */
@Question.meta(#{ id: "generics/contact-title" })
@Catalog.tag(TagName.title)
@UI.label("Title")
scalar ContactTitle extends string;
