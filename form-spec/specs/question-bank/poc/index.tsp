import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generics/index.tsp";

using SimplerForms;
using QuestionBank.Generics;

namespace QuestionBank.Poc;

/**
 * The person to contact about the application.
 *
 * Structurally a contact plus an address, and distinct from the representative who signs:
 * a point of contact answers questions, and forms routinely ask for both.
 */
@Question.meta(#{ id: "poc/details" })
@Catalog.entity(EntityName.poc)
@Catalog.tag(TagName.person, TagName.details)
@UI.label("Point of Contact")
@UI.order(
  QuestionPocDetails.name,
  QuestionPocDetails.title,
  QuestionPocDetails.address,
  QuestionPocDetails.phone,
  QuestionPocDetails.fax,
  QuestionPocDetails.email
)
model QuestionPocDetails extends QuestionContactDetails {
  @UI.label("Title")
  title?: ContactTitle;

  address: QuestionAddress;
}
