import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generics/index.tsp";

using SimplerForms;
using QuestionBank.Generics;

/**
 * What forms ask about the representative authorized to submit on the organization's behalf.
 *
 * These extend the generic shapes rather than being them, because a shape is not a question.
 * `generics/contact-title` says what a title looks like; `aor/title` is a thing a form asks
 * for, and it is the same thing whichever form asks -- which is what lets the bank answer
 * "which forms need an authorized representative's title" and what stops two forms declaring
 * it separately and drifting.
 *
 * The representative signs, and their signature carries the certification in 18 U.S.C. 1001,
 * so they are not interchangeable with a point of contact even where the shapes agree.
 */
namespace QuestionBank.Aor;

/** Enter the name of the authorized representative. */
@Question.meta(#{ id: "aor/name" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.person, TagName.name)
@UI.label("Authorized Representative")
model QuestionAorName extends QuestionPersonName {}

/** Enter the position title. */
@Question.meta(#{ id: "aor/title" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.title)
@UI.label("Title")
scalar AorTitle extends ContactTitle;

/** Enter a valid email Address. */
@Question.meta(#{ id: "aor/email" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.email)
@UI.label("Email")
scalar AorEmail extends EmailAddress;

/** Enter the daytime Telephone Number. */
@Question.meta(#{ id: "aor/phone" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.phone)
@UI.label("Telephone Number")
scalar AorPhone extends PhoneNumber;

/** Enter the Fax Number. */
@Question.meta(#{ id: "aor/fax" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.phone)
@UI.label("Fax Number")
scalar AorFax extends PhoneNumber;

/** Completed by Grants.gov upon submission. */
@Question.meta(#{ id: "aor/signature" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.person, TagName.name)
@UI.label("Signature of Authorized Representative")
scalar AorSignature extends Signature;

/** Completed by Grants.gov upon submission. */
@Question.meta(#{ id: "aor/date-signed" })
@Catalog.entity(EntityName.authorizedRepresentative)
@Catalog.tag(TagName.date)
@UI.label("Date Signed")
scalar AorDateSigned extends SubmittedDate;
