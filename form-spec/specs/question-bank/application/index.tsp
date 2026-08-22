import "@simpler-grants/form-spec";
import "../index.tsp";
import "../generics/index.tsp";

using SimplerForms;
using QuestionBank.Generics;

namespace QuestionBank.Application;

/** Completed by Grants.gov upon submission. */
@Question.meta(#{ id: "application/date-received" })
@Catalog.entity(EntityName.application)
@Catalog.tag(TagName.date)
@UI.label("Date Received")
scalar DateReceived extends SubmittedDate;
