import "@simpler-grants/form-spec";
import "../index.tsp";

using SimplerForms;

/**
 * Everything a form asks about the opportunity being applied to. Every one of these is
 * known before the applicant starts, which is why they all carry a pre-population rule
 * wherever a form composes them.
 */
namespace QuestionBank.Opportunity;

/** The awarding federal agency. */
@Question.meta(#{ id: "opportunity/agency-name" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.name, TagName.organization)
@UI.label("Agency Name")
@minLength(1)
@maxLength(60)
scalar AgencyName extends string;

/** The Assistance Listing (formerly CFDA) number. */
@Question.meta(#{ id: "opportunity/assistance-listing-number" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.identifier)
@UI.label("Assistance Listing Number")
@minLength(1)
@maxLength(15)
scalar AssistanceListingNumber extends string;

/** The Assistance Listing program title. */
@Question.meta(#{ id: "opportunity/assistance-listing-title" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.title)
@UI.label("Assistance Listing Title")
@minLength(1)
@maxLength(120)
scalar AssistanceListingTitle extends string;

/** The funding opportunity number. */
@Question.meta(#{ id: "opportunity/number" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.identifier)
@UI.label("Opportunity Number")
@minLength(1)
@maxLength(40)
scalar OpportunityNumber extends string;

/** The funding opportunity title. */
@Question.meta(#{ id: "opportunity/title" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.title)
@UI.label("Opportunity title")
@minLength(1)
@maxLength(255)
scalar OpportunityTitle extends string;

/** The competition number within the opportunity. */
@Question.meta(#{ id: "opportunity/competition-number" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.identifier)
@UI.label("Competition Number")
@minLength(1)
@maxLength(40)
scalar CompetitionNumber extends string;

/** The competition title within the opportunity. */
@Question.meta(#{ id: "opportunity/competition-title" })
@Catalog.entity(EntityName.opportunity)
@Catalog.tag(TagName.title)
@UI.label("Competition Title")
@minLength(1)
@maxLength(255)
scalar CompetitionTitle extends string;
