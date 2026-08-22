import "@simpler-grants/form-spec";
import "../index.tsp";

using SimplerForms;

namespace QuestionBank.Project;

/** Enter a brief, descriptive title of the project. */
@Question.meta(#{ id: "project/title" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.title)
@UI.label("Project Title")
@minLength(1)
@maxLength(200)
scalar ProjectTitle extends string;

/**
 * A congressional district, as a two-character state abbreviation and a three-character
 * district number: `CA-005`.
 */
@Question.meta(#{ id: "project/congressional-district" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.identifier)
@minLength(1)
@maxLength(6)
scalar CongressionalDistrict extends string;

/** Enter the date in the format MM/DD/YYYY. */
@Question.meta(#{ id: "project/start-date" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.date)
@UI.label("Project Start Date")
scalar ProjectStartDate extends plainDate;

/** Enter the date in the format MM/DD/YYYY. */
@Question.meta(#{ id: "project/end-date" })
@Catalog.entity(EntityName.project)
@Catalog.tag(TagName.date)
@UI.label("Project End Date")
scalar ProjectEndDate extends plainDate;
