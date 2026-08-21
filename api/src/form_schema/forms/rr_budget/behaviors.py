from typing import Any


class RRBudgetBehaviorError(ValueError):
    """Raised when source-bound budget behavior cannot be compiled exactly."""


_DECIMAL_PATTERN = r"^-?(?:\d{1,14}|\d{1,13}[.]\d|\d{1,12}[.]\d{2})$"


def normalize_source_decimal_fields(schema: dict[str, Any]) -> int:
    """Represent XSD decimal values as strings without floating-point loss."""

    count = 0

    def visit(node: object) -> None:
        nonlocal count
        if isinstance(node, dict):
            if node.get("type") == "number":
                node["type"] = "string"
                node["pattern"] = _DECIMAL_PATTERN
                node["minLength"] = 1
                node["maxLength"] = 16
                count += 1
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return count


def _source_path_index(schema: dict[str, Any]) -> dict[str, tuple[tuple[str, bool], ...]]:
    result: dict[str, tuple[tuple[str, bool], ...]] = {}

    def visit(node: dict[str, Any], path: tuple[tuple[str, bool], ...]) -> None:
        source_path = node.get("x-source-path")
        if isinstance(source_path, str):
            if source_path in result:
                raise RRBudgetBehaviorError(f"Duplicate source path: {source_path}")
            result[source_path] = path
        if node.get("type") == "object":
            for name, child in node.get("properties", {}).items():
                visit(child, path + ((name, False),))
        elif node.get("type") == "array":
            items = node.get("items")
            if not isinstance(items, dict):
                raise RRBudgetBehaviorError(f"Array has no item schema: {source_path}")
            if not path:
                raise RRBudgetBehaviorError("Root arrays are not supported")
            array_path = path[:-1] + ((path[-1][0], True),)
            visit(items, array_path)

    visit(schema, ())
    return result


def _dotted(path: tuple[tuple[str, bool], ...]) -> str:
    return ".".join(f"{name}[*]" if repeated else name for name, repeated in path)


def compile_source_resolved_sum_rules(
    schema: dict[str, Any], runtime_ast: dict[str, Any]
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Compile only source-resolved sums into Simpler's native dialect."""

    if runtime_ast.get("contract") != "source-bound-runtime-rule-ast/resolved-v1":
        raise RRBudgetBehaviorError("Unsupported R&R Budget runtime-rule contract")
    index = _source_path_index(schema)
    rule_schema: dict[str, Any] = {}
    compiled_ids: list[str] = []

    for rule in runtime_ast.get("rules", []):
        if rule.get("mechanism") != "calculation" or rule.get("execution_class") != "executable":
            continue
        if (
            rule.get("disposition") != "working"
            or rule.get("operator") != "sum"
            or rule.get("unresolved_references") != []
        ):
            raise RRBudgetBehaviorError(f"Unsupported executable rule: {rule.get('rule_id')}")

        target_source = rule["target"]["path"]
        target_path = index.get(target_source)
        if target_path is None:
            raise RRBudgetBehaviorError(f"Unknown calculation target: {target_source}")
        target_parent_source = target_source.rsplit(".", 1)[0]
        target_parent_path = target_path[:-1]
        fields: list[str] = []
        for operand in rule["operands"]:
            operand_source = operand["path"]
            operand_path = index.get(operand_source)
            if operand_path is None:
                raise RRBudgetBehaviorError(f"Unknown calculation operand: {operand_source}")
            if rule.get("instance_scope") == "same_instance":
                if not operand_source.startswith(f"{target_parent_source}."):
                    raise RRBudgetBehaviorError(
                        f"Same-instance operand escapes target parent: {operand_source}"
                    )
                if operand_path[: len(target_parent_path)] != target_parent_path:
                    raise RRBudgetBehaviorError(f"Runtime path drift: {operand_source}")
                relative = operand_path[len(target_parent_path) :]
                fields.append(f"@THIS.{_dotted(relative)}")
            elif rule.get("instance_scope") == "all_budget_periods":
                fields.append(_dotted(operand_path))
            else:
                raise RRBudgetBehaviorError(
                    f"Unsupported calculation scope: {rule.get('instance_scope')}"
                )

        current = rule_schema
        for name, repeated in target_path[:-1]:
            current = current.setdefault(name, {})
            if repeated:
                current["gg_type"] = "array"
        leaf = target_path[-1]
        if leaf[1] or leaf[0] in current:
            raise RRBudgetBehaviorError(f"Duplicate or array calculation target: {target_source}")
        current[leaf[0]] = {
            "gg_pre_population": {
                "rule": "sum_monetary",
                "fields": fields,
                "order": rule["source_index"] + 1,
            }
        }
        compiled_ids.append(rule["rule_id"])

    if len(compiled_ids) != 30:
        raise RRBudgetBehaviorError(f"Expected 30 executable sums, got {len(compiled_ids)}")
    return rule_schema, tuple(compiled_ids)
