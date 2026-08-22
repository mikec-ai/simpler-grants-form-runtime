import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generated/codes.tsp";

using SimplerForms;

namespace QuestionBank.Generics;

/** A person's name, in five parts. */
@Question.meta(#{ id: "generics/person-name" })
@Catalog.entity(EntityName.generic)
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
@Catalog.entity(EntityName.generic)
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

/**
 * A person and the ways to reach them.
 *
 * The shape only. Who the person *is* to the application -- a point of contact, the
 * representative authorized to sign -- is a different question, because the roles are not
 * interchangeable and a form asks for both. Those extend this.
 *
 * The person's title is deliberately not here. A point of contact may not have one; a
 * representative authorized to bind the organization does, because their title is how you
 * know they are authorized. So each of those declares it, with the optionality it has.
 */
@Question.meta(#{ id: "generics/contact-details" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.person, TagName.details)
@UI.label("Contact")
model QuestionContactDetails {
  @UI.label("Name")
  name: QuestionPersonName;

  @UI.label("Telephone Number")
  phone: PhoneNumber;

  @UI.label("Fax Number")
  fax?: PhoneNumber;

  @UI.label("Email")
  email: EmailAddress;
}

/** A telephone or fax number. */
@Question.meta(#{ id: "generics/phone" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.phone)
@minLength(1)
@maxLength(25)
scalar PhoneNumber extends string;

/** An email address. */
@Question.meta(#{ id: "generics/email" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.email)
@UI.label("Email")
@format("email")
@maxLength(60)
scalar EmailAddress extends string;

/** Enter the legal name of the organization. */
@Question.meta(#{ id: "generics/organization-name" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.organization, TagName.name)
@UI.label("Organization Name")
@minLength(1)
@maxLength(60)
scalar OrganizationName extends string;

/** Enter the position title. */
@Question.meta(#{ id: "generics/contact-title" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.title)
@UI.label("Title")
@minLength(1)
@maxLength(45)
scalar ContactTitle extends string;

// The answer to an attachment question is the uploaded file's id, not the file itself. A
// form's schema validates what an applicant submits, and an applicant does not author a
// file's name, size, or MIME type -- the server does. So the value is opaque here, and
// checking that it names a file actually attached to this application is a job for the
// runtime rather than for JSON Schema. That check is what SGG spells
// `gg_validation: attachment`, and `rules-sgg` derives it from this question's identity.
//
// What the reference resolves *to* is a separate type: `CommonGrants.Fields.File`
// (`downloadUrl`, `name`, `sizeInBytes`, `mimeType`, plus system metadata). The mapping
// from this question to that model is a lookup rather than a transformation, so it is
// one-way -- see `documentation/form-spec/deferred-designs.md`.
//
// A doc comment becomes the question's description, which applicants read. Rationale for
// the reader of this file goes in `//` comments, which no artifact carries.
/** Attach a file. */
@Question.meta(#{ id: "generics/attachment" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.attachment)
@format("uuid")
scalar AttachmentRef extends string;

/**
 * A dollar amount. Held as a string rather than a number so that a cent is never lost to
 * binary floating point.
 */
@Question.meta(#{ id: "generics/monetary-amount" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.money)
@pattern("^(-)?\\d*([.]\\d{2})?$")
@minLength(1)
@maxLength(14)
scalar MonetaryAmount extends string;

/** Completed by Grants.gov upon submission. */
@Question.meta(#{ id: "generics/signature" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.person, TagName.name)
@UI.label("Signature")
@minLength(1)
@maxLength(144)
scalar Signature extends string;

/** Completed by Grants.gov upon submission. */
@Question.meta(#{ id: "generics/submitted-date" })
@Catalog.entity(EntityName.generic)
@Catalog.tag(TagName.date)
@UI.label("Submitted Date")
scalar SubmittedDate extends plainDate;
