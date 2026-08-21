"""Source-pinned applicant presentation for PHS 398 Cover Page Supplement 5.0."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class PHS398CoverPagePresentationError(ValueError):
    """Raised when generated UI no longer matches the reviewed presentation map."""


_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "1. Vertebrate Animals Section",
        (
            "/properties/VertebrateAnimals/properties/AnimalEuthanasiaIndicator",
            "/properties/VertebrateAnimals/properties/AVMAConsistentIndicator",
            "/properties/VertebrateAnimals/properties/EuthanasiaMethodDescription",
        ),
    ),
    (
        "2. Program Income Section",
        (
            "/properties/ProgramIncome",
            "/properties/IncomeBudgetPeriod",
        ),
    ),
    (
        "3. Human Embryonic Stem Cells Section",
        (
            "/properties/StemCells/properties/isHumanStemCellsInvolved",
            "/properties/StemCells/properties/StemCellsIndicator",
            "/properties/StemCells/properties/CellLines",
        ),
    ),
    (
        "4. Human Fetal Tissue Section",
        (
            "/properties/isHumanFetalTissueInvolved",
            "/properties/ComplianceAssurance/properties/attFile",
            "/properties/HFTIRBConsentForm/properties/attFile",
        ),
    ),
    (
        "5. Inventions and Patents Section (for Renewal applications)",
        (
            "/properties/IsInventionsAndPatents",
            "/properties/IsPreviouslyReported",
        ),
    ),
    (
        "6. Change of Investigator/Change of Recipient Organization Section",
        (
            "/properties/IsChangeOfPDPI",
            "/properties/FormerPD_Name/properties/PrefixName",
            "/properties/FormerPD_Name/properties/FirstName",
            "/properties/FormerPD_Name/properties/MiddleName",
            "/properties/FormerPD_Name/properties/LastName",
            "/properties/FormerPD_Name/properties/SuffixName",
            "/properties/IsChangeOfInstitution",
            "/properties/FormerInstitutionName",
        ),
    ),
)


def _index_generated_nodes(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}

    def visit(node: dict[str, Any]) -> None:
        definition = node.get("definition")
        if isinstance(definition, str):
            if definition in indexed:
                raise PHS398CoverPagePresentationError(
                    f"Duplicate generated UI definition: {definition}"
                )
            indexed[definition] = node
            # A FieldList is one presentation unit; its row fields stay attached.
            if node.get("type") == "fieldList":
                return
        for child in node.get("children", []):
            visit(child)

    for node in nodes:
        visit(node)
    return indexed


def apply_pdf_presentation(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Arrange generated nodes in the six-section order of the pinned official PDF.

    This overlay changes only grouping and order. Generated definitions, widgets,
    conditions, and field-list children remain intact.
    """

    indexed = _index_generated_nodes(nodes)
    expected = {definition for _, definitions in _SECTIONS for definition in definitions}
    if set(indexed) != expected:
        missing = sorted(expected - set(indexed))
        unexpected = sorted(set(indexed) - expected)
        raise PHS398CoverPagePresentationError(
            f"Generated UI presentation drift; missing={missing}, unexpected={unexpected}"
        )

    sections: list[dict[str, Any]] = []
    for ordinal, (label, definitions) in enumerate(_SECTIONS, start=1):
        children = [deepcopy(indexed[definition]) for definition in definitions]
        if label == "2. Program Income Section":
            income_list = children[1]
            child_conditions = {
                repr(child.get("conditional")) for child in income_list.get("children", [])
            }
            if len(child_conditions) != 1 or any(
                child.get("conditional") is None for child in income_list.get("children", [])
            ):
                raise PHS398CoverPagePresentationError(
                    "Program-income row conditions no longer agree"
                )
            income_list["conditional"] = deepcopy(income_list["children"][0]["conditional"])
        sections.append(
            {
                "type": "section",
                "name": f"phs398-cover-page-section-{ordinal}",
                "label": label,
                "children": children,
            }
        )
    return sections
