import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generated/codes.tsp";

using SimplerForms;

namespace QuestionBank.Generics;

/** A person's name, in five parts. */
@Question.meta(#{ id: "generics/person-name" })
@Catalog.tag(TagName.person, TagName.name)
@UI.label("Name")
model QuestionPersonName {
  /** Enter the Prefix. */
  @UI.label("Prefix")
  @minLength(1)
  @maxLength(10)
  prefix?: string;

  /** Enter the First Name. */
  @UI.label("First Name")
  @minLength(1)
  @maxLength(35)
  firstName: string;

  /** Enter the Middle Name. */
  @UI.label("Middle Name")
  @minLength(1)
  @maxLength(25)
  middleName?: string;

  /** Enter the Last Name. */
  @UI.label("Last Name")
  @minLength(1)
  @maxLength(60)
  lastName: string;

  /** Enter the Suffix. */
  @UI.label("Suffix")
  @minLength(1)
  @maxLength(10)
  suffix?: string;
}

/** Enter an address. */
@Question.meta(#{ id: "generics/address" })
@Catalog.tag(TagName.address)
@UI.label("Address")
model QuestionAddress {
  /** Enter the first line of the Street Address. */
  @UI.label("Street 1")
  @minLength(1)
  @maxLength(55)
  street1: string;

  /** Enter the second line of the Street Address. */
  @UI.label("Street 2")
  @minLength(1)
  @maxLength(55)
  street2?: string;

  /** Enter the city. */
  @UI.label("City")
  @minLength(1)
  @maxLength(35)
  city: string;

  /** Enter the County or Parish. */
  @UI.label("County/Parish")
  @minLength(1)
  @maxLength(30)
  county?: string;

  /** Enter the state. */
  @UI.label("State")
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA)
  state?: StateCode;

  /** Enter the province. */
  @UI.label("Province")
  @minLength(1)
  @maxLength(30)
  province?: string;

  /** Enter the country. */
  @UI.label("Country")
  country: CountryCode;

  /** Enter the nine-digit Postal Code (e.g., ZIP Code). This field is required if the Country is the United States. */
  @UI.label("Zip / Postal Code")
  @minLength(1)
  @maxLength(30)
  @Validation.requiredWhen(QuestionAddress.country, CountryCode.USA)
  zipCode?: string;
}

/** A telephone or fax number. */
@Question.meta(#{ id: "generics/phone" })
@Catalog.tag(TagName.phone)
@minLength(1)
@maxLength(25)
scalar PhoneNumber extends string;

/** An email address. */
@Question.meta(#{ id: "generics/email" })
@Catalog.tag(TagName.email)
@UI.label("Email")
@format("email")
@maxLength(60)
scalar EmailAddress extends string;

/** Enter the legal name of the organization. */
@Question.meta(#{ id: "generics/organization-name" })
@Catalog.tag(TagName.organization, TagName.name)
@UI.label("Organization Name")
@minLength(1)
@maxLength(60)
scalar OrganizationName extends string;

/** Enter the position title. */
@Question.meta(#{ id: "generics/contact-title" })
@Catalog.tag(TagName.title)
@UI.label("Title")
@minLength(1)
@maxLength(45)
scalar ContactTitle extends string;
