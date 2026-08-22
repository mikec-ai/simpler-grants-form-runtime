528 fields across 20 forms.

## Candidate questions asked by 2+ forms

| Forms | Signal | Question | Asked as |
| --- | --- | --- | --- |
| 11 | shared reference | `common_shared_v1#organization_name` | applicant_name, applicant_organization, applicant_organization_name, organization_name, organizational_affiliation |
| 10 | shared reference | `common_shared_v1#contact_person_title` | aor_title, authorized_representative_title, contact_person_title, point_of_contact_title, title |
| 8 | shared reference | `common_shared_v1#signature` | aor_signature, authorized_representative_signature, signature |
| 8 | shared reference | `common_shared_v1#submitted_date` | authorized_representative_date_signed, date_signed, signed_date, submitted_date |
| 7 | shared reference | `common_shared_v1#attachment` | additional_congressional_districts, additional_locations_attachment, additional_project_title, areas_affected, att1 ... |
| 7 | same title and shape | `Prefix / string minLength=1 maxLength=10` | prefix |
| 7 | same title and shape | `First Name / string minLength=1 maxLength=35` | first_name |
| 7 | same title and shape | `Middle Name / string minLength=1 maxLength=25` | middle_name |
| 7 | same title and shape | `Last Name / string minLength=1 maxLength=60` | last_name |
| 7 | same title and shape | `Suffix / string minLength=1 maxLength=10` | suffix |
| 6 | shared reference | `common_shared_v1#phone_number` | authorized_representative_fax, authorized_representative_phone_number, fax, phone, phone_number ... |
| 6 | same title and shape | `Street 1 / string minLength=1 maxLength=55` | street1 |
| 6 | same title and shape | `Street 2 / string minLength=1 maxLength=55` | street2 |
| 6 | same title and shape | `City / string minLength=1 maxLength=35` | city |
| 6 | same title and shape | `State / string enum(71: AL: Alabama...)` | state |
| 6 | same title and shape | `Zip / Postal Code / string minLength=1 maxLength=30` | zip_code |
| 5 | shared reference | `common_shared_v1#contact_email` | authorized_representative_email, email, point_of_contact_email |
| 5 | same title and shape | `Country / string enum(261: AFG: AFGHANISTAN...)` | country |
| 4 | shared reference | `common_shared_v1#sam_uei` | sam_uei, uei |
| 4 | shared reference | `common_shared_v1#budget_monetary_amount` | applicant_amount, applicant_estimated_funding, award_amount, construction_amount, contractual_amount ... |
| 4 | same title and shape | `County/Parish / string minLength=1 maxLength=30` | county |
| 4 | same title and shape | `Province / string minLength=1 maxLength=30` | province |
| 3 | same title and shape | `Assistance Listing Number / string minLength=1 maxLength=15` | assistance_listing_number |
| 2 | same title and shape | `Funding Opportunity Number / string minLength=1 maxLength=40` | funding_opportunity_number |
| 2 | same title and shape | `Date Received / string date` | date_received |
| 2 | same title and shape | `EIN/TIN / string minLength=9 maxLength=30` | employer_taxpayer_identification_number |
| 2 | same title and shape | `Type of Applicant Other Explanation / string minLength=0 maxLength=30` | applicant_type_other_specify |
| 2 | same title and shape | `Assistance Listing Title / string minLength=1 maxLength=120` | assistance_listing_program_title |
| 2 | same title and shape | `Project Title / string minLength=1 maxLength=200` | project_title |
| 2 | same title and shape | `Project Start Date / string date` | project_start_date |
| 2 | same title and shape | `Project End Date / string date` | project_end_date |
| 2 | same title and shape | `Title / string minLength=1 maxLength=45` | authorized_representative_title |
| 2 | same field name and shape | `agency_name / string minLength=1 maxLength=60` | agency_name |
| 2 | same field name and shape | `funding_opportunity_title / string minLength=1 maxLength=255` | funding_opportunity_title |
| 2 | same field name and shape | `congressional_district_applicant / string minLength=1 maxLength=6` | congressional_district_applicant |
| 2 | same field name and shape | `applicant_type_code / string enum(24: A: State Government...)` | applicant_type_code |

92 candidates appear on one form only.

## Package candidates

| Group | Kind | Members | Forms | Side by side on |
| --- | --- | --- | --- | --- |
| `applicant-type` | answer and follow-up | applicant_type_code, applicant_type_other_specify | 2 | sf424, sf424_short |
| `construction-new-facilities` | answer and follow-up | construction_new_facilities, construction_new_facilities_explanation | 1 | epa_form_4700_4 |
| `additional-funding` | answer and follow-up | additional_funding, additional_funding_explanation | 1 | supplementary_neh_cover_sheet |
| `state-review` | answer and follow-up | state_review, state_review_available_date | 1 | sf424 |
| `civil-rights-lawsuit` | one question, composed more than once | civil_rights_lawsuit_question1, civil_rights_lawsuit_question2, civil_rights_lawsuit_question3 | 1 | epa_form_4700_4 |
| `congressional-district` | one question, composed more than once -- CONSTRAINTS DISAGREE | congressional_district, congressional_district_applicant, congressional_district_program_project | 4 | sf424 |
| `assistance-listing` | package | assistance_listing_number, assistance_listing_program_title | 5 | sf424, sf424_short |
| `authorized-representative` | package | authorized_representative_date_signed, authorized_representative_email, authorized_representative_fax, authorized_representative_phone_number, authorized_representative_signature, authorized_representative_title | 3 | gg_lobbying_form, sf424 |
| `funding-opportunity` | package | funding_opportunity_number, funding_opportunity_title | 3 | sf424, sf424_short |
| `point-of-contact` | package | point_of_contact_email, point_of_contact_name, point_of_contact_phone_number, point_of_contact_title | 1 | epa_form_4700_4 |
| `competition-identification` | package | competition_identification_number, competition_identification_title | 1 | sf424 |
| `material-change` | package | material_change_quarter, material_change_year | 1 | sflll |
