import uuid

from src.constants.lookup_constants import FormType
from src.db.models.competition_models import Form
from src.form_schema.components.contact_profile import build_contact_profile_component
from src.form_schema.shared import COMMON_SHARED_V1

_CONTACT_PROFILE = build_contact_profile_component("key_contacts").mount(
    "/properties/key_contacts/items"
)

FORM_JSON_SCHEMA = {
    "type": "object",
    # The applicant organization and at least one key contact are required,
    # matching the legacy XSD (ApplicantOrganizationName + RoleOnProject minOccurs=1).
    "required": ["applicant_organization_name", "key_contacts"],
    "properties": {
        "applicant_organization_name": {
            "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
            "title": "Applicant Organization Name",
            "description": "Enter the legal name of the applicant that will undertake the assistance activity. This field is required.",
        },
        "key_contacts": {
            "type": "array",
            "title": "Key Contacts",
            "description": "Enter between 1 and 4 key contacts and their role on the project.",
            # XSD RoleOnProject: minOccurs defaults to 1, maxOccurs=4
            "minItems": 1,
            "maxItems": 4,
            "items": {"$ref": "#/$defs/key_contact_person"},
        },
    },
    "$defs": {
        "key_contact_person": {
            "type": "object",
            "required": ["project_role", *_CONTACT_PROFILE.json_schema_definition["required"]],
            "properties": {
                "project_role": {
                    "type": "string",
                    "title": "Project Role",
                    "description": "Enter the individual's role on the project (e.g., project manager, fiscal contact).",
                    "minLength": 1,
                    "maxLength": 45,
                },
                "name": _CONTACT_PROFILE.json_schema_definition["properties"]["name"],
                "title": _CONTACT_PROFILE.json_schema_definition["properties"]["title"],
                "organizational_affiliation": {
                    "allOf": [{"$ref": COMMON_SHARED_V1.field_ref("organization_name")}],
                    "title": "Organizational Affiliation",
                    "description": "Enter the contact's organizational affiliation.",
                },
                # Full county/province address is the proven Key Contacts profile.
                "address": _CONTACT_PROFILE.json_schema_definition["properties"]["address"],
                "phone": _CONTACT_PROFILE.json_schema_definition["properties"]["phone"],
                "fax": _CONTACT_PROFILE.json_schema_definition["properties"]["fax"],
                "email": _CONTACT_PROFILE.json_schema_definition["properties"]["email"],
            },
        }
    },
}

FORM_UI_SCHEMA = [
    {
        "type": "section",
        "label": "Key Contacts",
        "name": "key_contacts",
        "description": "Enter between 1 and 4 key contacts and their role on the project.",
        "children": [
            # Applicant Organization Name is the first field and is not part of the FieldList.
            {
                "type": "field",
                "definition": "/properties/applicant_organization_name",
            },
            {
                "type": "fieldList",
                "name": "key_contacts",
                "label": "Key Contact",
                "description": "You may enter up to four (4) Key Contacts. At least 1 (one) contact person is required. Additional contacts are optional.",
                "children": [
                    {
                        "type": "field",
                        "definition": "/properties/key_contacts/items/properties/project_role",
                    },
                    *_CONTACT_PROFILE.ui_fields["name"],
                    *_CONTACT_PROFILE.ui_fields["title"],
                    {
                        "type": "field",
                        "definition": "/properties/key_contacts/items/properties/organizational_affiliation",
                    },
                    *_CONTACT_PROFILE.ui_fields["address"],
                    *_CONTACT_PROFILE.ui_fields["phone"],
                    *_CONTACT_PROFILE.ui_fields["fax"],
                    *_CONTACT_PROFILE.ui_fields["email"],
                ],
            },
        ],
    },
]


def _key_contact_xml_fields() -> dict:
    """XML field mappings for a single RoleOnProject entry.

    The RoleOnProject element and its direct children belong to the form
    namespace (default), while the contents of the HumanNameDataType and
    AddressDataTypeV3 types come from the GlobalLibrary namespace.
    """
    return {
        "project_role": {
            "xml_transform": {
                "target": "ContactProjectRole",
            }
        },
        "name": _CONTACT_PROFILE.xml_fields["name"],
        "title": _CONTACT_PROFILE.xml_fields["title"],
        "organizational_affiliation": {
            "xml_transform": {
                "target": "ContactOrganizationalAffiliation",
            }
        },
        # Order matches AddressDataTypeV3 XSD sequence.
        "address": _CONTACT_PROFILE.xml_fields["address"],
        "phone": _CONTACT_PROFILE.xml_fields["phone"],
        "fax": _CONTACT_PROFILE.xml_fields["fax"],
        "email": _CONTACT_PROFILE.xml_fields["email"],
    }


# XML Transformation Rules for Key Contacts v2.0
FORM_XML_TRANSFORM_RULES = {
    "_xml_config": {
        "description": "XML transformation rules for Key Contacts form",
        "version": "1.0",
        "form_name": "Key_Contacts_2_0",
        "namespaces": {
            "default": "http://apply.grants.gov/forms/Key_Contacts_2_0-V2.0",
            "Key_Contacts_2_0": "http://apply.grants.gov/forms/Key_Contacts_2_0-V2.0",
            "globLib": "http://apply.grants.gov/system/GlobalLibrary-V2.0",
            "codes": "http://apply.grants.gov/system/UniversalCodes-V2.0",
        },
        "xsd_url": "https://apply07.grants.gov/apply/forms/schemas/Key_Contacts_2_0-V2.0.xsd",
        "xml_structure": {
            "root_element": "Key_Contacts_2_0",
            "root_namespace_prefix": "Key_Contacts_2_0",
            "root_attributes": {
                "FormVersion": "2.0",
            },
        },
        "null_handling_options": {
            "exclude": "Default - exclude field entirely from XML (recommended)",
        },
    },
    # Field mappings - order matches XSD sequence
    "applicant_organization_name": {
        "xml_transform": {
            "target": "ApplicantOrganizationName",
        }
    },
    "key_contacts": {
        "xml_transform": {
            "target": "RoleOnProject",
            "type": "array",
        },
        "items": _key_contact_xml_fields(),
    },
}

KeyContacts_v2_0 = Form(
    # https://www.grants.gov/forms/form-items-description/fid/683
    form_id=uuid.UUID("f140c7db-724d-4954-bebd-081c0527908c"),
    legacy_form_id=683,
    form_name="KEY CONTACTS",
    short_form_name="Key_Contacts",
    form_version="2.0",
    agency_code="SGG",
    omb_number="4040-0010",
    form_json_schema=FORM_JSON_SCHEMA,
    form_ui_schema=FORM_UI_SCHEMA,
    # No rule schema needed — no conditional fields, attachments, or pre/post-population
    form_rule_schema=None,
    json_to_xml_schema=FORM_XML_TRANSFORM_RULES,
    form_instruction_id=uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479"),
    form_type=FormType.KEY_CONTACTS,
    sgg_version="1.0",
    is_deprecated=False,
)
