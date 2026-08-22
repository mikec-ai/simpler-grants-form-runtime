import "@simpler-grants/form-spec";
import "../index.tsp";

using SimplerForms;

namespace QuestionBank.PrimaryOrg;

/** UEI of the applicant organization. */
@Question.meta(#{ id: "primary-org/uei" })
@Catalog.entity(EntityName.primaryOrg)
@Catalog.tag(TagName.identifier, TagName.organization)
@UI.label("SAM UEI")
@minLength(12)
@maxLength(12)
scalar SamUei extends string;

/** Enter either TIN or EIN as assigned by the Internal Revenue Service. */
@Question.meta(#{ id: "primary-org/ein" })
@Catalog.entity(EntityName.primaryOrg)
@Catalog.tag(TagName.identifier, TagName.organization)
@UI.label("EIN/TIN")
@minLength(9)
@maxLength(30)
scalar EmployerIdentificationNumber extends string;
