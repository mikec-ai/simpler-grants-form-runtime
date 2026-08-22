from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree as lxml_etree

from src.form_schema.xml_plan import XMLPlanError
from src.form_schema.xml_plan import compile_xml_plan as _compile_xml_plan
from src.services.xml_generation.models import XMLGenerationRequest
from src.services.xml_generation.service import XMLGenerationService
from src.services.xml_generation.utils.attachment_mapping import AttachmentInfo

FORM_NS = "http://apply.grants.gov/forms/SF424D-V1.1"
GLOBAL_NS = "http://apply.grants.gov/system/Global-V1.0"
GLOBAL_LIBRARY_NS = "http://apply.grants.gov/system/GlobalLibrary-V2.0"
SOURCE_ROOT = Path(__file__).resolve().parents[3] / "src"
ROOT_XSD_PATH = "services/xml_generation/xsds/SF424D-V1.1.xsd"
SOURCE_MANIFEST = {"contract": "test-source-manifest/v1", "form_id": "SF424D"}


def compile_xml_plan(plan: object, runtime_profile: object | None = None) -> dict[str, object]:
    return _compile_xml_plan(
        plan,
        runtime_profile,
        source_root=SOURCE_ROOT,
        source_manifest=SOURCE_MANIFEST,
    )


def _provenance(selector: str) -> list[dict[str, str]]:
    return [
        {
            "path": ROOT_XSD_PATH,
            "source_ref": "https://apply07.grants.gov/apply/forms/schemas/SF424D-V1.1.xsd",
            "sha256": hashlib.sha256((SOURCE_ROOT / ROOT_XSD_PATH).read_bytes()).hexdigest(),
            "selector": selector,
        }
    ]


def _qname(namespace: str, local_name: str, prefix: str) -> dict[str, str]:
    return {
        "namespace": namespace,
        "local_name": local_name,
        "preferred_prefix": prefix,
    }


def _simple(
    order: int,
    namespace: str,
    local_name: str,
    prefix: str,
    value_origin: dict[str, str],
    *,
    minimum: int = 0,
    choice_group: dict[str, object] | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {
        "kind": "simple",
        "order": order,
        "qname": _qname(namespace, local_name, prefix),
        "min_occurs": minimum,
        "max_occurs": 1,
        "datatype": _qname("http://www.w3.org/2001/XMLSchema", "string", "xsd"),
        "value_origin": value_origin,
        "provenance": _provenance(f"xsd:element[@name='{local_name}']"),
    }
    if choice_group is not None:
        node["choice_group"] = choice_group
    return node


def _sf424d_plan() -> dict[str, object]:
    root_digest = hashlib.sha256((SOURCE_ROOT / ROOT_XSD_PATH).read_bytes()).hexdigest()
    root_source = {
        "path": ROOT_XSD_PATH,
        "source_ref": "https://apply07.grants.gov/apply/forms/schemas/SF424D-V1.1.xsd",
        "sha256": root_digest,
        "target_namespace": FORM_NS,
        "schema_version": "1.1",
        "role": "root",
    }
    return {
        "contract": "source-pinned-xml-plan/v1",
        "format_version": 1,
        "form": {"form_id": "SF424D", "form_version": "1.1"},
        "source_set": {
            "root_schema": root_source,
            "dependencies": [],
            "graph_sha256": hashlib.sha256(
                (json.dumps([root_source], indent=2, sort_keys=True) + "\n").encode()
            ).hexdigest(),
            "source_manifest_sha256": hashlib.sha256(
                (json.dumps(SOURCE_MANIFEST, indent=2, sort_keys=True) + "\n").encode()
            ).hexdigest(),
        },
        "document": {
            "namespaces": [
                {
                    "prefix": "SF424D",
                    "uri": FORM_NS,
                    "used_in_document": True,
                    "declare_in_output": True,
                },
                {
                    "prefix": "glob",
                    "uri": GLOBAL_NS,
                    "used_in_document": True,
                    "declare_in_output": True,
                },
                {
                    "prefix": "globLib",
                    "uri": GLOBAL_LIBRARY_NS,
                    "used_in_document": False,
                    "declare_in_output": True,
                },
            ],
            "root": {
                "qname": _qname(FORM_NS, "Assurances", "SF424D"),
                "attributes": [
                    {
                        "qname": _qname(FORM_NS, "programType", "SF424D"),
                        "use": "required",
                        "fixed_value": "Construction",
                        "value_origin": {"kind": "constant", "value": "Construction"},
                        "provenance": _provenance("xsd:attribute[@name='programType']"),
                    },
                    {
                        "qname": _qname(GLOBAL_NS, "coreSchemaVersion", "glob"),
                        "use": "required",
                        "fixed_value": "1.1",
                        "value_origin": {"kind": "constant", "value": "1.1"},
                        "provenance": _provenance("xsd:attribute[@name='coreSchemaVersion']"),
                    },
                ],
                "children": [
                    _simple(
                        0,
                        GLOBAL_NS,
                        "FormVersionIdentifier",
                        "glob",
                        {"kind": "constant", "value": "1.1"},
                        minimum=1,
                    ),
                    {
                        "kind": "object",
                        "order": 1,
                        "qname": _qname(FORM_NS, "AuthorizedRepresentative", "SF424D"),
                        "min_occurs": 0,
                        "max_occurs": 1,
                        "value_origin": {
                            "kind": "object",
                            "pointer": "/AuthorizedRepresentative",
                        },
                        "children": [
                            _simple(
                                0,
                                FORM_NS,
                                "RepresentativeName",
                                "SF424D",
                                {
                                    "kind": "application_pointer",
                                    "pointer": ("/AuthorizedRepresentative/RepresentativeName"),
                                },
                            ),
                            _simple(
                                1,
                                FORM_NS,
                                "RepresentativeTitle",
                                "SF424D",
                                {
                                    "kind": "application_pointer",
                                    "pointer": ("/AuthorizedRepresentative/RepresentativeTitle"),
                                },
                            ),
                        ],
                        "provenance": _provenance("xsd:element[@name='AuthorizedRepresentative']"),
                    },
                    _simple(
                        2,
                        FORM_NS,
                        "ApplicantOrganizationName",
                        "SF424D",
                        {
                            "kind": "application_pointer",
                            "pointer": "/ApplicantOrganizationName",
                        },
                    ),
                    _simple(
                        3,
                        FORM_NS,
                        "SubmittedDate",
                        "SF424D",
                        {"kind": "application_pointer", "pointer": "/SubmittedDate"},
                    ),
                ],
                "provenance": _provenance("xsd:element[@name='Assurances']"),
            },
        },
        "review_boundary": {
            "structural_facts": "deterministic_from_pinned_xsd",
            "application_pointers": "exact_source_paths_not_semantic_mappings",
            "semantic_mappings": [],
            "published_coverage_eligible": False,
        },
    }


def _reviewed_flat_profile() -> dict[str, object]:
    pointers = {
        "/AuthorizedRepresentative/RepresentativeName": "signature",
        "/AuthorizedRepresentative/RepresentativeTitle": "title",
        "/ApplicantOrganizationName": "applicant_organization",
        "/SubmittedDate": "date_signed",
    }
    review = {
        "status": "reviewed",
        "reviewed_by": "test-reviewer",
        "reviewed_at": "2026-08-20T12:00:00Z",
        "evidence_ref": "test://sf424d-runtime-profile-review",
    }
    profile: dict[str, object] = {
        "contract": "simpler-xml-runtime-profile/v1",
        "profile_id": "sf424d-flat-test-v1",
        "review": review,
        "bindings": {
            pointer: {"runtime_path": path, "review": review} for pointer, path in pointers.items()
        },
        "legacy_namespaces": [
            {
                "prefix": "att",
                "uri": "http://apply.grants.gov/system/Attachments-V1.0",
                "evidence": "legacy_observed",
            }
        ],
    }
    profile["profile_sha256"] = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return profile


def _tree(xml: str) -> tuple[object, object, list[tuple[object, object]]]:
    root = lxml_etree.fromstring(xml.encode())
    return (
        root.tag,
        tuple(sorted(root.attrib.items())),
        [
            (child.tag, child.text, [(nested.tag, nested.text) for nested in child])
            for child in root
        ],
    )


def test_canonical_and_reviewed_flat_profiles_are_wire_equivalent() -> None:
    plan = _sf424d_plan()
    canonical = compile_xml_plan(plan)
    flat = compile_xml_plan(plan, _reviewed_flat_profile())
    service = XMLGenerationService()

    canonical_xml = service.generate_xml(
        XMLGenerationRequest(
            application_data={
                "AuthorizedRepresentative": {
                    "RepresentativeName": "M & H",
                    "RepresentativeTitle": "Director",
                },
                "ApplicantOrganizationName": "Org <One>",
                "SubmittedDate": "2026-08-20",
            },
            transform_config=canonical,
        )
    )
    flat_xml = service.generate_xml(
        XMLGenerationRequest(
            application_data={
                "signature": "M & H",
                "title": "Director",
                "applicant_organization": "Org <One>",
                "date_signed": "2026-08-20",
            },
            transform_config=flat,
        )
    )

    assert canonical_xml.success is True
    assert flat_xml.success is True
    assert _tree(canonical_xml.xml_data) == _tree(flat_xml.xml_data)
    assert list(canonical) == [
        "_xml_config",
        "constant_0_FormVersionIdentifier",
        "AuthorizedRepresentative",
        "ApplicantOrganizationName",
        "SubmittedDate",
    ]
    assert "att" not in canonical["_xml_config"]["namespaces"]
    assert "att" in flat["_xml_config"]["namespaces"]


def test_compiled_plan_preserves_source_and_node_provenance() -> None:
    transform = compile_xml_plan(_sf424d_plan())

    assert (
        transform["_xml_config"]["source_plan"]["source_set"]["root_schema"]["sha256"]
        == hashlib.sha256((SOURCE_ROOT / ROOT_XSD_PATH).read_bytes()).hexdigest()
    )
    assert transform["SubmittedDate"]["_provenance"] == _provenance(
        "xsd:element[@name='SubmittedDate']"
    )
    assert transform == compile_xml_plan(_sf424d_plan())


def test_generated_xml_validates_against_local_xsd_without_network() -> None:
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={
                "AuthorizedRepresentative": {
                    "RepresentativeName": "Mike",
                    "RepresentativeTitle": "Director",
                },
                "ApplicantOrganizationName": "HHS",
                "SubmittedDate": "2026-08-20",
            },
            transform_config=compile_xml_plan(_sf424d_plan()),
        )
    )
    assert response.success is True

    xsd_dir = Path(__file__).resolve().parents[3] / "src" / "services" / "xml_generation" / "xsds"

    class OfflineResolver(lxml_etree.Resolver):
        def resolve(self, url, public_id, context):
            local_path = xsd_dir / Path(url).name
            if local_path.exists():
                return self.resolve_filename(str(local_path), context)
            return None

    parser = lxml_etree.XMLParser(no_network=True)
    parser.resolvers.add(OfflineResolver())
    schema_document = lxml_etree.parse(str(xsd_dir / "SF424D-V1.1.xsd"), parser)
    schema = lxml_etree.XMLSchema(schema_document)
    schema.assertValid(lxml_etree.fromstring(response.xml_data.encode()))


def test_invalid_or_unreviewed_input_fails_closed() -> None:
    profile = _reviewed_flat_profile()
    profile["bindings"]["/SubmittedDate"]["review"]["status"] = "agent_proposed"
    profile["profile_sha256"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in profile.items() if key != "profile_sha256"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with pytest.raises(XMLPlanError, match="status is not reviewed"):
        compile_xml_plan(_sf424d_plan(), profile)

    bad_order = deepcopy(_sf424d_plan())
    bad_order["document"]["root"]["children"][0]["order"] = 1
    bad_order["document"]["root"]["children"][1]["order"] = 0
    with pytest.raises(XMLPlanError, match="contiguous XSD order"):
        compile_xml_plan(bad_order)

    unresolved = deepcopy(_sf424d_plan())
    unresolved["document"]["root"]["children"][2]["value_origin"] = {"kind": "unresolved"}
    with pytest.raises(XMLPlanError, match="runtime value.*unresolved"):
        compile_xml_plan(unresolved)


def test_source_pins_review_boundary_and_canonical_pointers_are_verified() -> None:
    bad_hash = _sf424d_plan()
    bad_hash["source_set"]["root_schema"]["sha256"] = "0" * 64
    with pytest.raises(XMLPlanError, match="does not match the pinned source bytes"):
        compile_xml_plan(bad_hash)

    bad_manifest = _sf424d_plan()
    bad_manifest["source_set"]["source_manifest_sha256"] = "0" * 64
    with pytest.raises(XMLPlanError, match="does not match the supplied source manifest"):
        compile_xml_plan(bad_manifest)

    wrong_namespace = _sf424d_plan()
    wrong_namespace["document"]["root"]["qname"]["namespace"] = "urn:wrong"
    with pytest.raises(XMLPlanError, match="root namespace does not match"):
        compile_xml_plan(wrong_namespace)

    wrong_version = _sf424d_plan()
    wrong_version["form"]["form_version"] = "9.9"
    with pytest.raises(XMLPlanError, match="form version does not match"):
        compile_xml_plan(wrong_version)

    empty_boundary = _sf424d_plan()
    empty_boundary["review_boundary"] = {}
    with pytest.raises(XMLPlanError, match="review_boundary"):
        compile_xml_plan(empty_boundary)

    unsupported_coverage = _sf424d_plan()
    unsupported_coverage["review_boundary"]["published_coverage_eligible"] = True
    with pytest.raises(XMLPlanError, match="cannot claim published coverage"):
        compile_xml_plan(unsupported_coverage)

    unrelated_pointer = _sf424d_plan()
    unrelated_pointer["document"]["root"]["children"][2]["value_origin"][
        "pointer"
    ] = "/totally_different"
    with pytest.raises(XMLPlanError, match="does not match XML target"):
        compile_xml_plan(unrelated_pointer)

    compiled = compile_xml_plan(_sf424d_plan(), _reviewed_flat_profile())
    persisted_profile = compiled["_xml_config"]["source_plan"]["runtime_profile"]
    assert persisted_profile["profile_id"] == "sf424d-flat-test-v1"
    assert persisted_profile["review"]["evidence_ref"].startswith("test://")


def test_occurrence_bounds_and_typed_lowercase_attribute_constants_are_enforced() -> None:
    plan = _sf424d_plan()
    plan["document"]["root"]["attributes"].append(
        {
            "qname": _qname(FORM_NS, "policy", "SF424D"),
            "use": "required",
            "value_origin": {"kind": "constant", "value": "construction"},
            "provenance": _provenance("xsd:attribute[@name='policy']"),
        }
    )
    required_org = plan["document"]["root"]["children"][2]
    required_org["min_occurs"] = 1
    transform = compile_xml_plan(plan)
    service = XMLGenerationService()

    missing = service.generate_xml(
        XMLGenerationRequest(application_data={}, transform_config=transform)
    )
    present = service.generate_xml(
        XMLGenerationRequest(
            application_data={"ApplicantOrganizationName": "HHS"},
            transform_config=transform,
        )
    )

    assert missing.success is False
    assert "requires 1..1 occurrences; found 0" in missing.error_message
    assert present.success is True
    root = lxml_etree.fromstring(present.xml_data.encode())
    assert root.get(f"{{{FORM_NS}}}policy") == "construction"

    array_plan = _sf424d_plan()
    array_plan["document"]["root"]["attributes"] = []
    array_plan["document"]["root"]["children"] = [
        {
            "kind": "array",
            "order": 0,
            "qname": _qname(FORM_NS, "Code", "SF424D"),
            "min_occurs": 1,
            "max_occurs": 2,
            "value_origin": {"kind": "array", "pointer": "/Code"},
            "children": [],
            "provenance": _provenance("xsd:element[@name='Code']"),
        }
    ]
    array_transform = compile_xml_plan(array_plan)
    too_many = service.generate_xml(
        XMLGenerationRequest(
            application_data={"Code": ["one", "two", "three"]},
            transform_config=array_transform,
        )
    )
    assert too_many.success is False
    assert "requires 1..2 occurrences; found 3" in too_many.error_message

    null_constant = _sf424d_plan()
    null_constant["document"]["root"]["children"][0]["value_origin"]["value"] = None
    with pytest.raises(XMLPlanError, match="cannot have a null value"):
        compile_xml_plan(null_constant)


def test_dotted_and_nested_occurrence_and_choice_constraints_are_enforced() -> None:
    dotted = _sf424d_plan()
    dotted["document"]["root"]["attributes"] = []
    dotted["document"]["root"]["children"] = [
        _simple(
            0,
            FORM_NS,
            "Value",
            "SF424D",
            {"kind": "application_pointer", "pointer": "/Group/Value"},
            minimum=1,
        )
    ]
    dotted_response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={"Group": {"Value": "present"}},
            transform_config=compile_xml_plan(dotted),
        )
    )
    assert dotted_response.success
    dotted_root = lxml_etree.fromstring(dotted_response.xml_data.encode())
    assert dotted_root.find(f"{{{FORM_NS}}}Value").text == "present"

    choice = {
        "group_id": "nested-choice",
        "exclusive": True,
        "min_occurs": 1,
        "max_occurs": 1,
    }
    nested = _sf424d_plan()
    nested["document"]["root"]["attributes"] = []
    nested["document"]["root"]["children"] = [
        {
            "kind": "object",
            "order": 0,
            "qname": _qname(FORM_NS, "Box", "SF424D"),
            "min_occurs": 1,
            "max_occurs": 1,
            "value_origin": {"kind": "object", "pointer": "/Box"},
            "children": [
                _simple(
                    0,
                    FORM_NS,
                    "A",
                    "SF424D",
                    {"kind": "application_pointer", "pointer": "/Box/A"},
                    choice_group=choice,
                ),
                _simple(
                    1,
                    FORM_NS,
                    "B",
                    "SF424D",
                    {"kind": "application_pointer", "pointer": "/Box/B"},
                    choice_group=choice,
                ),
            ],
            "provenance": _provenance("xsd:element[@name='Box']"),
        }
    ]
    transform = compile_xml_plan(nested)
    service = XMLGenerationService()
    assert service.generate_xml(
        XMLGenerationRequest(application_data={"Box": {"A": "one"}}, transform_config=transform)
    ).success
    invalid = service.generate_xml(
        XMLGenerationRequest(
            application_data={"Box": {"A": "one", "B": "two"}},
            transform_config=transform,
        )
    )
    assert invalid.success is False
    assert "nested-choice" in invalid.error_message


def test_repeating_objects_and_cross_namespace_children_compile_generically() -> None:
    plan = _sf424d_plan()
    plan["form"] = {"form_id": "Contacts", "form_version": "1.1"}
    plan["document"]["namespaces"].append(
        {
            "prefix": "contactTypes",
            "uri": "https://example.test/contact-types",
            "used_in_document": True,
            "declare_in_output": True,
        }
    )
    plan["document"]["root"]["attributes"] = []
    plan["document"]["root"]["children"] = [
        {
            "kind": "array",
            "order": 0,
            "qname": _qname(FORM_NS, "RoleOnProject", "SF424D"),
            "min_occurs": 1,
            "max_occurs": 4,
            "value_origin": {"kind": "array", "pointer": "/RoleOnProject"},
            "children": [
                _simple(
                    0,
                    FORM_NS,
                    "ContactProjectRole",
                    "SF424D",
                    {
                        "kind": "application_pointer",
                        "pointer": "/RoleOnProject/ContactProjectRole",
                    },
                    minimum=1,
                ),
                {
                    "kind": "object",
                    "order": 1,
                    "qname": _qname(FORM_NS, "ContactName", "SF424D"),
                    "min_occurs": 1,
                    "max_occurs": 1,
                    "value_origin": {
                        "kind": "object",
                        "pointer": "/RoleOnProject/ContactName",
                    },
                    "children": [
                        _simple(
                            0,
                            "https://example.test/contact-types",
                            "FirstName",
                            "contactTypes",
                            {
                                "kind": "application_pointer",
                                "pointer": "/RoleOnProject/ContactName/FirstName",
                            },
                            minimum=1,
                        )
                    ],
                    "provenance": _provenance("xsd:element[@name='ContactName']"),
                },
            ],
            "provenance": _provenance("xsd:element[@name='RoleOnProject']"),
        }
    ]
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={
                "RoleOnProject": [
                    {
                        "ContactProjectRole": "Director",
                        "ContactName": {"FirstName": "Mike"},
                    },
                    {
                        "ContactProjectRole": "Counsel",
                        "ContactName": {"FirstName": "Laura"},
                    },
                ]
            },
            transform_config=compile_xml_plan(plan),
        )
    )
    assert response.success is True
    root = lxml_etree.fromstring(response.xml_data.encode())
    roles = root.findall(f"{{{FORM_NS}}}RoleOnProject")
    assert len(roles) == 2
    for role, expected in zip(roles, ("Mike", "Laura"), strict=True):
        name = role.find(f"{{{FORM_NS}}}ContactName")
        assert name.find("{https://example.test/contact-types}FirstName").text == expected


def test_identical_local_names_keep_their_per_instance_qnames() -> None:
    other_namespace = "https://example.test/other"
    plan = _sf424d_plan()
    plan["document"]["namespaces"].append(
        {
            "prefix": "other",
            "uri": other_namespace,
            "used_in_document": True,
            "declare_in_output": True,
        }
    )
    plan["document"]["root"]["attributes"] = []

    def container(order: int, name: str, namespace: str, prefix: str) -> dict[str, object]:
        return {
            "kind": "object",
            "order": order,
            "qname": _qname(namespace, name, prefix),
            "min_occurs": 1,
            "max_occurs": 1,
            "value_origin": {"kind": "object", "pointer": f"/{name}"},
            "children": [
                _simple(
                    0,
                    namespace,
                    "City",
                    prefix,
                    {"kind": "application_pointer", "pointer": f"/{name}/City"},
                    minimum=1,
                )
            ],
            "provenance": _provenance(f"xsd:element[@name='{name}']"),
        }

    plan["document"]["root"]["children"] = [
        container(0, "FormAddress", FORM_NS, "SF424D"),
        container(1, "OtherAddress", other_namespace, "other"),
    ]
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={
                "FormAddress": {"City": "Baltimore"},
                "OtherAddress": {"City": "Ottawa"},
            },
            transform_config=compile_xml_plan(plan),
        )
    )
    assert response.success
    root = lxml_etree.fromstring(response.xml_data.encode())
    assert root.find(f"{{{FORM_NS}}}FormAddress/{{{FORM_NS}}}City").text == "Baltimore"
    assert (
        root.find(f"{{{other_namespace}}}OtherAddress/{{{other_namespace}}}City").text == "Ottawa"
    )


def test_exclusive_choices_are_enforced_at_root_and_in_array_rows() -> None:
    choice = {"group_id": "state-or-province", "exclusive": True, "min_occurs": 1, "max_occurs": 1}
    plan = _sf424d_plan()
    plan["document"]["root"]["attributes"] = []
    plan["document"]["root"]["children"] = [
        _simple(
            0,
            FORM_NS,
            "State",
            "SF424D",
            {"kind": "application_pointer", "pointer": "/State"},
            choice_group=choice,
        ),
        _simple(
            1,
            FORM_NS,
            "Province",
            "SF424D",
            {"kind": "application_pointer", "pointer": "/Province"},
            choice_group=choice,
        ),
    ]
    transform = compile_xml_plan(plan)
    service = XMLGenerationService()

    valid = service.generate_xml(
        XMLGenerationRequest(application_data={"State": "MD"}, transform_config=transform)
    )
    both = service.generate_xml(
        XMLGenerationRequest(
            application_data={"State": "MD", "Province": "Ontario"},
            transform_config=transform,
        )
    )
    neither = service.generate_xml(
        XMLGenerationRequest(application_data={}, transform_config=transform)
    )

    assert valid.success is True
    assert both.success is False
    assert "requires 1..1 members" in both.error_message
    assert neither.success is False
    assert "requires 1..1 members" in neither.error_message

    array_plan = _sf424d_plan()
    array_plan["document"]["root"]["attributes"] = []
    array_plan["document"]["root"]["children"] = [
        {
            "kind": "array",
            "order": 0,
            "qname": _qname(FORM_NS, "Address", "SF424D"),
            "min_occurs": 0,
            "max_occurs": 4,
            "value_origin": {"kind": "array", "pointer": "/Address"},
            "children": [
                _simple(
                    0,
                    FORM_NS,
                    "State",
                    "SF424D",
                    {"kind": "application_pointer", "pointer": "/Address/State"},
                    choice_group=choice,
                ),
                _simple(
                    1,
                    FORM_NS,
                    "Province",
                    "SF424D",
                    {"kind": "application_pointer", "pointer": "/Address/Province"},
                    choice_group=choice,
                ),
            ],
            "provenance": _provenance("xsd:element[@name='Address']"),
        }
    ]
    invalid_row = service.generate_xml(
        XMLGenerationRequest(
            application_data={"Address": [{"State": "MD", "Province": "Ontario"}]},
            transform_config=compile_xml_plan(array_plan),
        )
    )
    assert invalid_row.success is False
    assert "Address.0" in invalid_row.error_message


def test_nested_and_multiple_attachments_compile_without_form_specific_rules() -> None:
    plan = _sf424d_plan()
    plan["form"] = {"form_id": "AttachmentProof", "form_version": "1.1"}
    plan["document"]["namespaces"].append(
        {
            "prefix": "att",
            "uri": "http://apply.grants.gov/system/Attachments-V1.0",
            "used_in_document": True,
            "declare_in_output": True,
        }
    )
    plan["document"]["root"]["attributes"] = []
    plan["document"]["root"]["children"] = [
        {
            "kind": "object",
            "order": 0,
            "qname": _qname(FORM_NS, "ComplianceAssurance", "SF424D"),
            "min_occurs": 0,
            "max_occurs": 1,
            "value_origin": {"kind": "object", "pointer": "/ComplianceAssurance"},
            "children": [
                {
                    "kind": "attachment",
                    "order": 0,
                    "qname": _qname(FORM_NS, "attFile", "SF424D"),
                    "min_occurs": 0,
                    "max_occurs": 1,
                    "attachment": {
                        "cardinality": "single",
                        "minimum_files": 0,
                        "maximum_files": 1,
                    },
                    "value_origin": {
                        "kind": "attachment",
                        "pointer": "/ComplianceAssurance/attFile",
                    },
                    "provenance": _provenance("xsd:element[@name='attFile']"),
                }
            ],
            "provenance": _provenance("xsd:element[@name='ComplianceAssurance']"),
        },
        {
            "kind": "attachment",
            "order": 1,
            "qname": _qname(FORM_NS, "Appendix", "SF424D"),
            "min_occurs": 0,
            "max_occurs": 100,
            "attachment": {
                "cardinality": "multiple",
                "minimum_files": 0,
                "maximum_files": 100,
            },
            "value_origin": {"kind": "attachment", "pointer": "/Appendix"},
            "provenance": _provenance("xsd:element[@name='Appendix']"),
        },
    ]
    mapping = {
        attachment_id: AttachmentInfo(
            filename=f"{attachment_id}.pdf",
            mime_type="application/pdf",
            file_location=f"s3://bucket/{attachment_id}.pdf",
            hash_value="YWJj",
        )
        for attachment_id in ("one", "two", "three")
    }
    response = XMLGenerationService().generate_xml(
        XMLGenerationRequest(
            application_data={
                "ComplianceAssurance": {"attFile": "one"},
                "Appendix": ["two", "three"],
            },
            transform_config=compile_xml_plan(plan),
            attachment_mapping=mapping,
        )
    )
    assert response.success is True
    root = lxml_etree.fromstring(response.xml_data.encode())
    assert root.find(f"{{{FORM_NS}}}ComplianceAssurance/{{{FORM_NS}}}attFile") is not None
    appendix = root.find(f"{{{FORM_NS}}}Appendix")
    assert (
        len(appendix.findall("{http://apply.grants.gov/system/Attachments-V1.0}AttachedFile")) == 2
    )


def test_attachment_occurrence_and_choice_constraints_are_preserved() -> None:
    choice = {
        "group_id": "text-or-file",
        "exclusive": True,
        "min_occurs": 1,
        "max_occurs": 1,
    }
    plan = _sf424d_plan()
    plan["document"]["root"]["attributes"] = []
    plan["document"]["root"]["children"] = [
        _simple(
            0,
            FORM_NS,
            "Narrative",
            "SF424D",
            {"kind": "application_pointer", "pointer": "/Narrative"},
            choice_group=choice,
        ),
        {
            "kind": "attachment",
            "order": 1,
            "qname": _qname(FORM_NS, "File", "SF424D"),
            "min_occurs": 0,
            "max_occurs": 1,
            "choice_group": choice,
            "attachment": {
                "cardinality": "single",
                "minimum_files": 0,
                "maximum_files": 1,
            },
            "value_origin": {"kind": "attachment", "pointer": "/File"},
            "provenance": _provenance("xsd:element[@name='File']"),
        },
    ]
    mapping = {
        "file": AttachmentInfo(
            filename="file.pdf",
            mime_type="application/pdf",
            file_location="s3://bucket/file.pdf",
            hash_value="YWJj",
        )
    }
    transform = compile_xml_plan(plan)
    service = XMLGenerationService()
    missing = service.generate_xml(
        XMLGenerationRequest(application_data={}, transform_config=transform)
    )
    file_selected = service.generate_xml(
        XMLGenerationRequest(
            application_data={"File": "file"},
            transform_config=transform,
            attachment_mapping=mapping,
        )
    )
    empty_array = service.generate_xml(
        XMLGenerationRequest(application_data={"File": []}, transform_config=transform)
    )
    narrative_selected = service.generate_xml(
        XMLGenerationRequest(application_data={"Narrative": "inline"}, transform_config=transform)
    )
    assert missing.success is False
    assert file_selected.success is True
    assert empty_array.success is False
    assert narrative_selected.success is True

    required = deepcopy(plan)
    required_file = required["document"]["root"]["children"][1]
    required_file.pop("choice_group")
    required_file["order"] = 0
    required_file["min_occurs"] = 1
    required["document"]["root"]["children"] = [required_file]
    required_missing = service.generate_xml(
        XMLGenerationRequest(application_data={}, transform_config=compile_xml_plan(required))
    )
    assert required_missing.success is False
    assert "requires 1..1 occurrences" in required_missing.error_message

    nested = _sf424d_plan()
    nested["document"]["root"]["attributes"] = []
    nested_file = deepcopy(required_file)
    nested_file["value_origin"]["pointer"] = "/Box/File"
    nested["document"]["root"]["children"] = [
        {
            "kind": "object",
            "order": 0,
            "qname": _qname(FORM_NS, "Box", "SF424D"),
            "min_occurs": 1,
            "max_occurs": 1,
            "value_origin": {"kind": "object", "pointer": "/Box"},
            "children": [nested_file],
            "provenance": _provenance("xsd:element[@name='Box']"),
        }
    ]
    nested_missing = service.generate_xml(
        XMLGenerationRequest(
            application_data={"Box": {}}, transform_config=compile_xml_plan(nested)
        )
    )
    assert nested_missing.success is False
    assert "requires 1..1 occurrences" in nested_missing.error_message

    nested_choice = deepcopy(nested)
    first = nested_choice["document"]["root"]["children"][0]["children"][0]
    first["min_occurs"] = 0
    first["choice_group"] = choice
    second = deepcopy(first)
    second["order"] = 1
    second["qname"] = _qname(FORM_NS, "OtherFile", "SF424D")
    second["value_origin"]["pointer"] = "/Box/OtherFile"
    nested_choice["document"]["root"]["children"][0]["children"].append(second)
    choice_missing = service.generate_xml(
        XMLGenerationRequest(
            application_data={"Box": {}},
            transform_config=compile_xml_plan(nested_choice),
        )
    )
    assert choice_missing.success is False
    assert "Attachment choice group 'text-or-file'" in choice_missing.error_message


def test_unsupported_attachment_and_flattened_namespace_shapes_fail_closed() -> None:
    attachment = {
        "kind": "attachment",
        "order": 0,
        "qname": _qname(FORM_NS, "File", "SF424D"),
        "min_occurs": 0,
        "max_occurs": 1,
        "attachment": {
            "cardinality": "single",
            "minimum_files": 0,
            "maximum_files": 1,
        },
        "value_origin": {"kind": "attachment", "pointer": "/Box/File"},
        "provenance": _provenance("xsd:element[@name='File']"),
    }

    mixed = _sf424d_plan()
    box = mixed["document"]["root"]["children"][1]
    box["order"] = 0
    box["qname"] = _qname(FORM_NS, "Box", "SF424D")
    box["value_origin"] = {"kind": "object", "pointer": "/Box"}
    box["children"] = [
        _simple(
            0,
            FORM_NS,
            "Label",
            "SF424D",
            {"kind": "application_pointer", "pointer": "/Box/Label"},
        ),
        {**attachment, "order": 1},
    ]
    mixed["document"]["root"]["children"] = [box]
    with pytest.raises(XMLPlanError, match="mixes attachment and ordinary children"):
        compile_xml_plan(mixed)

    array_nested = _sf424d_plan()
    array_nested["document"]["root"]["children"] = [
        {
            "kind": "array",
            "order": 0,
            "qname": _qname(FORM_NS, "Row", "SF424D"),
            "min_occurs": 0,
            "max_occurs": 4,
            "value_origin": {"kind": "array", "pointer": "/Row"},
            "children": [attachment],
            "provenance": _provenance("xsd:element[@name='Row']"),
        }
    ]
    with pytest.raises(XMLPlanError, match="nested below an array"):
        compile_xml_plan(array_nested)

    cross_namespace = _sf424d_plan()
    cross_namespace["document"]["namespaces"].append(
        {
            "prefix": "other",
            "uri": "https://example.test/other",
            "used_in_document": True,
            "declare_in_output": True,
        }
    )
    cross_namespace["document"]["root"]["children"] = [
        {
            **attachment,
            "qname": _qname("https://example.test/other", "File", "other"),
            "value_origin": {"kind": "attachment", "pointer": "/File"},
        }
    ]
    with pytest.raises(XMLPlanError, match="changes namespace"):
        compile_xml_plan(cross_namespace)

    unrelated_attachment = _sf424d_plan()
    unrelated_attachment["document"]["root"]["children"] = [
        {
            **attachment,
            "value_origin": {"kind": "attachment", "pointer": "/totally_different"},
        }
    ]
    with pytest.raises(XMLPlanError, match="does not match XML target"):
        compile_xml_plan(unrelated_attachment)

    flattened = _sf424d_plan()
    flattened["document"]["namespaces"].append(
        {
            "prefix": "other",
            "uri": "https://example.test/other",
            "used_in_document": True,
            "declare_in_output": True,
        }
    )
    flattened["document"]["root"]["children"][1]["children"][0]["qname"] = _qname(
        "https://example.test/other", "RepresentativeName", "other"
    )
    with pytest.raises(XMLPlanError, match="qualified flattened bindings"):
        compile_xml_plan(flattened, _reviewed_flat_profile())
