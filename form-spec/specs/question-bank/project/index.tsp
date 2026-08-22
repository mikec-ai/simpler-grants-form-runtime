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
