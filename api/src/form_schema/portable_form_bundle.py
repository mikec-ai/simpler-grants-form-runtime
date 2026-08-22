"""Compile portable declarations through the native resolved-package seam."""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
import re
from pathlib import Path
from typing import Any

from src.form_schema.portable_form_kernel import (
    CONTRACT,
    PortableFormKernel,
    PortableFormKernelError,
    load_portable_form_kernel,
)
from src.form_schema.resolved_form_package import (
    PORTABLE_RESOLVED_CONTRACT,
    ResolvedFormPackage,
    create_resolved_form_package,
)

PortableFormBundleError = PortableFormKernelError


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise PortableFormBundleError(f"{label} must be an object with string keys")
    return value


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PortableFormBundleError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PortableFormBundleError(f"{label} must be a non-empty string")
    return value


def _ui_name(label: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return name or "section"


def _adapt_ui_node(
    node: object,
    label: str,
    *,
    item_prefix: str | None = None,
) -> list[dict[str, Any]]:
    value = _object(node, label)
    node_type = _string(value.get("type"), f"{label}.type")
    if node_type == "Control":
        allowed = {"type", "scope", "label", "description", "options", "conditional"}
        unknown = set(value) - allowed
        if unknown:
            raise PortableFormBundleError(f"{label} has unknown Control keys: {sorted(unknown)}")
        scope = _string(value.get("scope"), f"{label}.scope")
        if not scope.startswith("#/"):
            raise PortableFormBundleError(f"{label}.scope must begin with #/")
        definition = scope[1:]
        if item_prefix is not None:
            definition = f"{item_prefix}{definition}"
        options = _object(value["options"], f"{label}.options") if "options" in value else {}
        detail = options.get("detail")
        if detail is not None:
            detail_value = _object(detail, f"{label}.options.detail")
            detail_type = _string(detail_value.get("type"), f"{label}.options.detail.type")
            if detail_type not in {"VerticalLayout", "Group"}:
                raise PortableFormBundleError(
                    f"{label}.options.detail.type is unsupported: {detail_type}"
                )
            detail_elements = _array(
                detail_value.get("elements"), f"{label}.options.detail.elements"
            )
            item_label = _string(
                options.get("itemLabel", value.get("label", "Item")),
                f"{label}.options.itemLabel",
            )
            field_list: dict[str, Any] = {
                "type": "fieldList",
                "name": definition.rsplit("/", 1)[-1],
                "label": item_label,
                "children": list(
                    itertools.chain.from_iterable(
                        _adapt_ui_node(
                            child,
                            f"{label}.options.detail.elements[{index}]",
                            item_prefix=f"{definition}/items",
                        )
                        for index, child in enumerate(detail_elements)
                    )
                ),
            }
            if "description" in value:
                field_list["description"] = _string(value["description"], f"{label}.description")
            return [field_list]

        simpler = _object(options.get("simpler", {}), f"{label}.options.simpler")
        native_type = simpler.get("type", "field")
        if native_type not in {"field", "null"}:
            raise PortableFormBundleError(f"{label}.options.simpler.type is unsupported")
        result: dict[str, Any] = {"type": native_type, "definition": definition}
        for key in ("label", "description"):
            if key in value:
                result[key] = _string(value[key], f"{label}.{key}")
        native_widget = simpler.get("widget")
        if native_widget is not None:
            result["widget"] = _string(native_widget, f"{label}.options.simpler.widget")
        remaining_options = {key: item for key, item in options.items() if key != "simpler"}
        if remaining_options:
            result["options"] = remaining_options
        if "conditional" in value:
            result["conditional"] = _object(value["conditional"], f"{label}.conditional")
        return [result]

    if node_type not in {"VerticalLayout", "Group"}:
        raise PortableFormBundleError(f"{label}.type is unsupported: {node_type}")
    allowed = {"type", "label", "elements", "options"}
    unknown = set(value) - allowed
    if unknown:
        raise PortableFormBundleError(f"{label} has unknown layout keys: {sorted(unknown)}")
    elements = _array(value.get("elements"), f"{label}.elements")
    children = list(
        itertools.chain.from_iterable(
            _adapt_ui_node(child, f"{label}.elements[{index}]", item_prefix=item_prefix)
            for index, child in enumerate(elements)
        )
    )
    section_label = _string(value.get("label", "Form"), f"{label}.label")
    layout_options = _object(value["options"], f"{label}.options") if "options" in value else {}
    simpler = _object(layout_options.get("simpler", {}), f"{label}.options.simpler")
    native_name = simpler.get("name")
    if native_name is not None:
        native_name = _string(native_name, f"{label}.options.simpler.name")
    return [
        {
            "type": "section",
            "label": section_label,
            "name": native_name or _ui_name(section_label),
            "children": children,
        }
    ]


def _compiler_sha256() -> str:
    paths = [Path(__file__).resolve(), Path(__file__).with_name("portable_form_kernel.py")]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclasses.dataclass(frozen=True)
class PortableFormBundle:
    """Thin Simpler adapter over a dependency-neutral portable kernel."""

    kernel: PortableFormKernel

    @property
    def root(self) -> Path:
        return self.kernel.root

    @property
    def manifest(self) -> dict[str, Any]:
        return self.kernel.manifest

    @property
    def schemas_by_id(self) -> dict[str, dict[str, Any]]:
        return self.kernel.schemas_by_id

    @property
    def forms_by_key(self) -> dict[str, Any]:
        return self.kernel.forms_by_key

    @property
    def compatibility_records(self) -> tuple[dict[str, Any], ...]:
        return self.kernel.compatibility_records

    @property
    def dependency_paths(self) -> tuple[Path, ...]:
        return self.kernel.dependency_paths

    @property
    def bundle_digest(self) -> str:
        return self.kernel.bundle_digest

    def to_resolved_package(self, form_key: str) -> ResolvedFormPackage:
        """Compile one declaration through the single immutable package seam."""

        if form_key not in self.kernel.forms_by_key:
            raise PortableFormBundleError(f"unknown portable form_key: {form_key}")
        portable = self.kernel.forms_by_key[form_key]
        definition = portable.definition
        metadata = {**definition["metadata"]}
        metadata.setdefault("form_instruction_id", None)
        targets = portable.mappings["targets"]
        common_grants = targets.get("common_grants", {"from": {}, "to": {}})
        resolved_schema = self.kernel.resolved_schema(form_key)
        resolved_schema["x-portable-form-bundle"] = {
            "contract": CONTRACT,
            "bundle_digest": self.kernel.bundle_digest,
            "form_key": form_key,
            "question_bindings": definition["question_bindings"],
            "review_boundary": definition["review_boundary"],
        }
        compiler_sha256 = _compiler_sha256()
        manifest = {
            "contract": PORTABLE_RESOLVED_CONTRACT,
            "source_set": {
                "bundle_contract": CONTRACT,
                "bundle_digest": self.kernel.bundle_digest,
                "evidence": definition["source_evidence"],
            },
            "compiler": {
                "name": "portable-form-kernel-to-simpler-resolved-package",
                "version": "0.2.0",
                "verification": "content_addressed",
                "sha256": compiler_sha256,
            },
            "form": metadata,
            "question_bindings": definition["question_bindings"],
            "review_boundary": definition["review_boundary"],
        }
        return create_resolved_form_package(
            manifest=manifest,
            json_schema=resolved_schema,
            ui_schema=(
                list(
                    itertools.chain.from_iterable(
                        _adapt_ui_node(node, f"forms.{form_key}.ui.elements[{index}]")
                        for index, node in enumerate(
                            _array(portable.ui.get("elements"), f"forms.{form_key}.ui.elements")
                        )
                    )
                )
                if portable.ui.get("type") == "VerticalLayout"
                else _adapt_ui_node(portable.ui, f"forms.{form_key}.ui")
            ),
            mappings={
                "x-mapping-from-cg": common_grants["from"],
                "x-mapping-to-cg": common_grants["to"],
            },
            xml_transform=targets.get("grants_gov_xml", {}).get("runtime_transform"),
            rule_schema=portable.rules,
            dependency_paths=self.kernel.dependency_paths,
        )

    def to_form(self, form_key: str) -> Any:
        """Materialize a native Form only through the resolved-package adapter."""

        return self.to_resolved_package(form_key).to_form()

    def analysis_projection(self) -> dict[str, Any]:
        return self.kernel.analysis_projection()


def load_portable_form_bundle(root: Path) -> PortableFormBundle:
    """Load portable declarations, then expose the thin Simpler adapter."""

    return PortableFormBundle(kernel=load_portable_form_kernel(root))
