import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generics/index.tsp";

using SimplerForms;
using QuestionBank.Generics;

namespace QuestionBank.Poc;

/** A point of contact: name, title, address, and contact methods. */
@Question.meta(#{ id: "poc/details" })
@Catalog.entity(EntityName.poc)
@Catalog.tag(TagName.person, TagName.details)
@UI.label("Point of Contact")
model QuestionPocDetails {
  name: QuestionPersonName;

  @UI.label("Title")
  title?: ContactTitle;

  address: QuestionAddress;

  @UI.label("Telephone Number")
  phone: PhoneNumber;

  @UI.label("Fax Number")
  fax?: PhoneNumber;

  @UI.label("Email")
  email: EmailAddress;
}
