Compared 15 of 20 forms against their own XML transform.

## Forms whose JSON shape disagrees with their own wire format

| Form | Path | Disagreement |
| --- | --- | --- |
| sf424a | `forecasted_cash_needs` | JSON nests, wire is flat |
| sflll | `reporting_entity.tier` | wire nests, JSON is flat |

## Where the same property holds different members

| Property | Members | Wire element | Asked by |
| --- | --- | --- | --- |
| `address` | city, country, county, province, state, street1, street2, zip_code | -- | key_contacts, project_performance_site_location |
| `address` | city, country, county, province, state, street1, street2, zip_code | Address | project_performance_site_location, sf424_short |
| `address` | city, country, state, street1, street2, zip_code | Address | epa_key_contacts |
| `address` | city, state, street1, street2, zip_code | -- | sflll |
| `address` | city, state, street1, street2, zip_code | Address | sflll |
| `authorized_representative` | address, email, fax, name, phone, title | AuthorizedRepresentative | epa_key_contacts |
| `authorized_representative` | first_name, last_name, middle_name, prefix, suffix | AuthorizedRepresentative | sf424, sf424_short |
| `contact_person` | address, email, fax, name, phone_number, title | ContactPersonGroup | sf424_short |
| `contact_person` | first_name, last_name, middle_name, prefix, suffix | ContactName | cd511 |
| `contact_person` | first_name, last_name, middle_name, prefix, suffix | ContactPerson | sf424 |
