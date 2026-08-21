from typing import Any


def _field(ui_schema: list[dict], definition: str) -> dict:
    matches = [
        child
        for section in ui_schema
        for child in section["children"]
        if child.get("definition") == definition
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one R&R SF-424 UI field for {definition}")
    return matches[0]


def _remove_field(ui_schema: list[dict], definition: str) -> None:
    field = _field(ui_schema, definition)
    matches = [section for section in ui_schema if field in section["children"]]
    if len(matches) != 1:
        raise ValueError(f"Expected one R&R SF-424 UI section for {definition}")
    matches[0]["children"].remove(field)


def _root_equals(pointer: str, value: str) -> dict:
    return {
        "op": "equals",
        "ref": {"scope": "root", "pointer": pointer},
        "value": value,
    }


def _show_when(predicate: dict) -> dict:
    return {
        "when": predicate,
        "then": {"visible": True},
        "otherwise": {"visible": False},
    }


def _all(*predicates: dict) -> dict:
    return {"op": "all", "predicates": list(predicates)}


def apply_source_reviewed_behaviors(artifacts: dict[str, Any]) -> None:
    """Apply the exact behavior subset supported by the current Simpler runtime.

    These bindings come from the pinned DAT/PDF/XFA review. They remain explicitly
    coverage-ineligible; this function does not infer or parse prose at runtime.
    """

    schema = artifacts["json-schema.json"]
    ui_schema = artifacts["ui-schema.json"]
    rules = artifacts["rule-schema.json"]

    application_type = schema["properties"]["ApplicationType"]
    application_type.setdefault("allOf", []).append({
        "if": {
            "properties": {
                "isOtherAgencySubmission": {"const": "Y: Yes"},
            },
            "required": ["isOtherAgencySubmission"],
        },
        "then": {"required": ["OtherAgencySubmissionExplanation"]},
    })
    application_type["allOf"].extend([
        {
            "if": {
                "properties": {"ApplicationTypeCode": {"const": "Revision"}},
                "required": ["ApplicationTypeCode"],
            },
            "then": {"required": ["RevisionCode"]},
        },
        {
            "if": {
                "properties": {
                    "ApplicationTypeCode": {"const": "Revision"},
                    "RevisionCode": {"const": "E"},
                },
                "required": ["ApplicationTypeCode", "RevisionCode"],
            },
            "then": {"required": ["RevisionCodeOtherExplanation"]},
        },
    ])
    revision_code = application_type["properties"]["RevisionCode"]
    revision_code["x-encoded-checkbox-group"] = {
        "choices": [
            {"code": "A", "label": "A. Increase Award"},
            {"code": "B", "label": "B. Decrease Award"},
            {"code": "C", "label": "C. Increase Duration"},
            {"code": "D", "label": "D. Decrease Duration"},
            {"code": "E", "label": "E. Other"},
        ],
        "combinations": [
            {"value": value, "members": list(value)} for value in revision_code["enum"]
        ],
    }
    applicant_type = schema["properties"]["ApplicantType"]
    applicant_type.setdefault("allOf", []).append({
        "if": {
            "properties": {"ApplicantTypeCode": {"const": "X: Other (specify)"}},
            "required": ["ApplicantTypeCode"],
        },
        "then": {"required": ["ApplicantTypeCodeOtherExplanation"]},
    })
    state_review = schema["properties"]["StateReview"]
    state_review.setdefault("allOf", []).append({
        "if": {
            "properties": {"StateReviewCodeType": {"const": "Y: Yes"}},
            "required": ["StateReviewCodeType"],
        },
        "then": {"required": ["StateReviewDate"]},
    })
    schema.setdefault("allOf", []).extend([
        {
            "if": {
                "properties": {
                    "ApplicationType": {
                        "properties": {
                            "ApplicationTypeCode": {"enum": ["Renewal", "Continuation", "Revision"]}
                        },
                        "required": ["ApplicationTypeCode"],
                    }
                },
                "required": ["ApplicationType"],
            },
            "then": {"required": ["FederalID"]},
        },
        {
            "if": {
                "properties": {"SubmissionTypeCode": {"const": "Change/Corrected Application"}},
                "required": ["SubmissionTypeCode"],
            },
            "then": {"required": ["GGTrackingID"]},
        },
    ])

    schema["properties"]["TrustAgree"]["enum"] = ["Y: Yes"]
    schema["properties"]["TrustAgree"]["const"] = "Y: Yes"
    for path in (
        ("ApplicantInfo", "ContactPersonInfo", "Email"),
        ("PDPIContactInfo", "Email"),
        ("AORInfo", "Email"),
    ):
        node = schema["properties"]
        for index, segment in enumerate(path):
            node = node[segment] if index == len(path) - 1 else node[segment]["properties"]
        node["format"] = "email"
    sam_uei = schema["properties"]["ApplicantInfo"]["properties"]["OrganizationInfo"]["properties"][
        "SAMUEI"
    ]
    sam_uei.update({"minLength": 12, "maxLength": 12})

    applicant_district = schema["properties"]["CongressionalDistrict"]["properties"][
        "ApplicantCongressionalDistrict"
    ]
    applicant_district["pattern"] = r"^(?:[A-Z]{2}|00)-[0-9]{3}$"

    funding = schema["properties"]["EstimatedProjectFunding"]["properties"]
    for field_name in (
        "TotalEstimatedAmount",
        "TotalNonfedrequested",
        "TotalfedNonfedrequested",
        "EstimatedProgramIncome",
    ):
        # The source constrains precision but does not calculate any of these
        # four independently entered funding answers.
        funding[field_name]["multipleOf"] = 0.01

    # These values are supplied only during submission. Keeping them required in
    # the authoring schema makes every ordinary GET/MODIFY state invalid while the
    # disabled controls are still empty.
    for submission_managed in ("AOR_Signature", "AOR_SignedDate"):
        schema["required"].remove(submission_managed)

    conditions = {
        "/properties/GGTrackingID": _root_equals(
            "/SubmissionTypeCode", "Change/Corrected Application"
        ),
        "/properties/ApplicationType/properties/OtherAgencySubmissionExplanation": (
            _root_equals("/ApplicationType/isOtherAgencySubmission", "Y: Yes")
        ),
        "/properties/ApplicantType/properties/ApplicantTypeCodeOtherExplanation": (
            _root_equals("/ApplicantType/ApplicantTypeCode", "X: Other (specify)")
        ),
        "/properties/StateReview/properties/StateReviewDate": _root_equals(
            "/StateReview/StateReviewCodeType", "Y: Yes"
        ),
        "/properties/ApplicantType/properties/SmallBusinessOrganizationType/properties/isSociallyEconomicallyDisadvantaged": _root_equals(
            "/ApplicantType/ApplicantTypeCode", "R: Small Business"
        ),
        "/properties/ApplicantType/properties/SmallBusinessOrganizationType/properties/isWomenOwned": _root_equals(
            "/ApplicantType/ApplicantTypeCode", "R: Small Business"
        ),
        "/properties/ApplicationType/properties/RevisionCode": _root_equals(
            "/ApplicationType/ApplicationTypeCode", "Revision"
        ),
        "/properties/ApplicationType/properties/RevisionCodeOtherExplanation": _all(
            _root_equals("/ApplicationType/ApplicationTypeCode", "Revision"),
            _root_equals("/ApplicationType/RevisionCode", "E"),
        ),
    }
    for definition, predicate in conditions.items():
        _field(ui_schema, definition)["conditional"] = _show_when(predicate)
    _field(
        ui_schema,
        "/properties/ApplicationType/properties/RevisionCode",
    )["widget"] = "EncodedCheckboxGroup"

    _remove_field(
        ui_schema,
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/EIN",
    )
    for definition in (
        "/properties/FederalAgencyName",
        "/properties/CFDANumber",
        "/properties/ActivityTitle",
        "/properties/ApplicantInfo/properties/OrganizationInfo/properties/SAMUEI",
        "/properties/AOR_Signature",
        "/properties/AOR_SignedDate",
    ):
        _field(ui_schema, definition)["type"] = "null"

    rules.update({
        "FederalAgencyName": {"gg_pre_population": {"rule": "agency_name"}},
        "CFDANumber": {"gg_pre_population": {"rule": "assistance_listing_number"}},
        "ActivityTitle": {"gg_pre_population": {"rule": "assistance_listing_program_title"}},
        "ApplicantInfo": {"OrganizationInfo": {"SAMUEI": {"gg_pre_population": {"rule": "uei"}}}},
        "AOR_Signature": {"gg_post_population": {"rule": "signature"}},
        "AOR_SignedDate": {"gg_post_population": {"rule": "current_date"}},
    })
    applicant_rules = rules.setdefault("ApplicantInfo", {})
    applicant_rules.setdefault("OrganizationInfo", {}).setdefault("Address", {})["Country"] = {
        "gg_pre_population": {
            "rule": "default_value",
            "value": "USA: UNITED STATES",
        }
    }
    applicant_rules.setdefault("ContactPersonInfo", {}).setdefault("Address", {})["Country"] = {
        "gg_pre_population": {
            "rule": "default_value",
            "value": "USA: UNITED STATES",
        }
    }

    # The source form initially copies applicant organization/address answers into
    # both role-specific profiles, but explicitly allows applicants to overwrite
    # them. Order 2 ensures the applicant country default has run first.
    source_organization = "ApplicantInfo.OrganizationInfo"
    for target_profile in ("PDPIContactInfo", "AORInfo"):
        target_rules = rules.setdefault(target_profile, {})
        for field_name in ("OrganizationName", "Department", "Division"):
            target_rules[field_name] = {
                "gg_pre_population": {
                    "rule": "copy_if_missing",
                    "source_field": f"{source_organization}.{field_name}",
                    "order": 2,
                }
            }
        target_address_rules = target_rules.setdefault("Address", {})
        for field_name in (
            "Street1",
            "Street2",
            "City",
            "County",
            "State",
            "Province",
            "Country",
            "ZipPostalCode",
        ):
            target_address_rules[field_name] = {
                "gg_pre_population": {
                    "rule": "copy_if_missing",
                    "source_field": f"{source_organization}.Address.{field_name}",
                    "order": 2,
                }
            }

    application_type_rules = rules.setdefault("ApplicationType", {})
    application_type_rules["RevisionCode"] = {
        "gg_pre_population": {
            "rule": "clear_unless_all_equal",
            "conditions": [{"field": "ApplicationType.ApplicationTypeCode", "value": "Revision"}],
            "order": 1,
        }
    }
    application_type_rules["RevisionCodeOtherExplanation"] = {
        "gg_pre_population": {
            "rule": "clear_unless_all_equal",
            "conditions": [
                {"field": "ApplicationType.ApplicationTypeCode", "value": "Revision"},
                {"field": "ApplicationType.RevisionCode", "value": "E"},
            ],
            "order": 2,
        }
    }
    rules.setdefault("ProposedProjectPeriod", {})["ProposedEndDate"] = {
        "gg_validation": {
            "rule": "date_not_before",
            "other_field": "ProposedProjectPeriod.ProposedStartDate",
        }
    }
