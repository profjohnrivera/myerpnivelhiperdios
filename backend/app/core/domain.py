# backend/app/core/domain.py

from typing import List, Tuple, Any, Dict, Union


_NULL_SENTINELS = (None, False)


class DomainEngine:
    @staticmethod
    def _get_nested_value(record_instance: Any, field_path: str) -> Any:
        parts = field_path.split(".")
        current_val = record_instance
        for part in parts:
            if hasattr(current_val, part):
                try:
                    current_val = getattr(current_val, part)
                except ValueError:
                    return None
            else:
                return None
            if current_val is None:
                break
        return current_val

    @staticmethod
    def _evaluate_leaf(
        leaf: Tuple,
        record_data: Dict[str, Any],
        record_instance: Any = None,
    ) -> bool:
        if len(leaf) != 3:
            return False

        field, operator, value = leaf

        if "." in field and record_instance:
            record_value = DomainEngine._get_nested_value(record_instance, field)
        else:
            record_value = record_data.get(field)

        if hasattr(record_value, "id"):
            record_value = record_value.id

        if field == "id" or field.endswith("_id"):
            if isinstance(record_value, str) and record_value.isdigit():
                record_value = int(record_value)
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            elif isinstance(value, (list, tuple, set)):
                value = [
                    int(v) if isinstance(v, str) and v.isdigit() else v
                    for v in value
                ]

        op = str(operator).lower()

        if op == "=?":
            return record_value in _NULL_SENTINELS or record_value == value

        if op == "=" and value in _NULL_SENTINELS:
            return record_value in _NULL_SENTINELS
        if op == "!=" and value in _NULL_SENTINELS:
            return record_value not in _NULL_SENTINELS

        if op == "=":
            return record_value == value
        if op == "!=":
            return record_value != value
        if op in ("in", "not in"):
            if not isinstance(value, (list, tuple, set)):
                value = [value]
            result = record_value in value
            return result if op == "in" else not result
        if op == ">":
            return record_value is not None and record_value > value
        if op == "<":
            return record_value is not None and record_value < value
        if op == ">=":
            return record_value is not None and record_value >= value
        if op == "<=":
            return record_value is not None and record_value <= value
        if op in ("like", "ilike"):
            if record_value is None:
                return False
            left, right = str(record_value), str(value)
            return right.lower() in left.lower() if op == "ilike" else right in left
        if op == "not ilike":
            if record_value is None:
                return True
            return str(value).lower() not in str(record_value).lower()
        if op == "not like":
            if record_value is None:
                return True
            return str(value) not in str(record_value)

        return False

    @staticmethod
    def check(
        record_data: Dict[str, Any],
        domain: List[Union[str, Tuple]],
        record_instance: Any = None,
    ) -> bool:
        if not domain:
            return True

        has_ops = any(
            isinstance(item, str) and item in ("&", "|", "!") for item in domain
        )

        if not has_ops:
            return all(
                DomainEngine._evaluate_leaf(item, record_data, record_instance)
                for item in domain
                if isinstance(item, (tuple, list))
            )

        stack: List[bool] = []
        for item in reversed(domain):
            if isinstance(item, str):
                op = item.upper()
                if op == "!" and stack:
                    stack.append(not stack.pop())
                elif op in ("&", "|") and len(stack) >= 2:
                    left, right = stack.pop(), stack.pop()
                    stack.append((left and right) if op == "&" else (left or right))
            elif isinstance(item, (tuple, list)):
                stack.append(
                    DomainEngine._evaluate_leaf(item, record_data, record_instance)
                )

        return all(stack) if stack else True

    @staticmethod
    def compile_sql(
        domain: List[Union[str, Tuple]],
        base_model: str,
    ) -> Tuple[str, str, List[Any]]:
        if not domain:
            return "", "", []

        from app.core.registry import Registry

        joins: List[str] = []
        params: List[Any] = []
        join_map: Dict[Tuple[str, str], str] = {}
        alias_counter = 0

        def get_alias() -> str:
            nonlocal alias_counter
            alias_counter += 1
            return f"t{alias_counter}"

        def normalize_like(raw: Any) -> str:
            s = str(raw or "")
            return s if ("%" in s or "_" in s) else f"%{s}%"

        def schema_fields(model_name: str) -> Dict[str, Any]:
            return Registry.get_schema_fields_for_model(model_name)

        def process_leaf(leaf: Tuple) -> str:
            if len(leaf) != 3:
                return "TRUE"

            field_path, op, value = leaf
            op_str = str(op).lower()

            if op_str == "=?":
                if value in _NULL_SENTINELS or value == "":
                    return "TRUE"
                op_str = "="

            parts = field_path.split(".")
            current_model = base_model
            current_alias = "t0"

            for rel_field in parts[:-1]:
                fields_cfg = schema_fields(current_model)
                meta = fields_cfg.get(rel_field, {})
                target_model = meta.get("target") or meta.get("relation")
                if not target_model:
                    raise ValueError(
                        f"Domain Compiler Error: Relación '{rel_field}' "
                        f"no existe en '{current_model}'"
                    )

                join_key = (current_alias, rel_field)
                if join_key not in join_map:
                    alias = get_alias()
                    join_map[join_key] = alias
                    target_table = target_model.replace(".", "_")
                    joins.append(
                        f'LEFT JOIN "{target_table}" {alias} '
                        f'ON {current_alias}."{rel_field}" = {alias}.id'
                    )

                current_alias = join_map[join_key]
                current_model = target_model

            final_field = parts[-1]
            fields_cfg = schema_fields(current_model)
            is_native = final_field in fields_cfg or final_field == "id"
            f_type = (
                fields_cfg.get(final_field, {}).get("type")
                if final_field != "id"
                else "integer"
            )

            field_ref = (
                f'{current_alias}."{final_field}"'
                if is_native
                else f"{current_alias}.x_ext->>'{final_field}'"
            )

            if value in _NULL_SENTINELS and op_str in ("=", "!="):
                return (
                    f"{field_ref} IS NULL"
                    if op_str == "="
                    else f"{field_ref} IS NOT NULL"
                )

            is_numeric = (
                f_type in ("relation", "many2one", "integer", "int")
                or final_field == "id"
            )

            if is_numeric:
                if isinstance(value, (list, tuple, set)):
                    cleaned = [
                        int(v) if isinstance(v, str) and v.isdigit() else v
                        for v in value
                        if isinstance(v, int) or (isinstance(v, str) and v.isdigit())
                    ]
                    value = cleaned
                    if op_str in ("in", "not in") and not value:
                        return "FALSE" if op_str == "in" else "TRUE"
                elif isinstance(value, str) and value.isdigit():
                    value = int(value)
                elif isinstance(value, str) and op_str not in (
                    "like",
                    "ilike",
                    "not like",
                    "not ilike",
                ):
                    return "FALSE"

            if op_str in ("child_of", "parent_of"):
                if isinstance(value, (list, tuple, set)):
                    value = [int(v) for v in value if str(v).isdigit()]
                    if not value:
                        return "FALSE"
                    params.append(value)
                    return f'{field_ref} = ANY(${len(params)}::bigint[])'
                if isinstance(value, str) and value.isdigit():
                    value = int(value)
                params.append(value)
                return f"{field_ref} = ${len(params)}"

            if op_str in ("like", "ilike", "not like", "not ilike"):
                value = normalize_like(value)

            params.append(value)
            idx = len(params)

            if op_str == "=":
                return f"{field_ref} = ${idx}"
            if op_str == "!=":
                return f"{field_ref} != ${idx}"
            if op_str == ">":
                return f"{field_ref} > ${idx}"
            if op_str == "<":
                return f"{field_ref} < ${idx}"
            if op_str == ">=":
                return f"{field_ref} >= ${idx}"
            if op_str == "<=":
                return f"{field_ref} <= ${idx}"

            if op_str in ("in", "not in"):
                cast = "bigint[]" if is_numeric else "text[]"
                if not isinstance(value, (list, tuple, set)):
                    params[-1] = [value]
                return (
                    f"{field_ref} = ANY(${idx}::{cast})"
                    if op_str == "in"
                    else f"{field_ref} != ALL(${idx}::{cast})"
                )

            if op_str == "like":
                return f"{field_ref} LIKE ${idx}"
            if op_str == "ilike":
                return f"{field_ref} ILIKE ${idx}"
            if op_str == "not like":
                return f"{field_ref} NOT LIKE ${idx}"
            if op_str == "not ilike":
                return f"{field_ref} NOT ILIKE ${idx}"

            raise ValueError(f"Operador de dominio no soportado: '{op}'")

        has_explicit_ops = any(
            isinstance(item, str) and item in ("&", "|", "!") for item in domain
        )

        if not has_explicit_ops:
            leaves_sql = [
                process_leaf(item)
                for item in domain
                if isinstance(item, (tuple, list))
            ]
            return " ".join(joins), " AND ".join(leaves_sql), params

        stack: List[str] = []
        for item in reversed(domain):
            if isinstance(item, str):
                op = item.upper()
                if op == "!" and stack:
                    stack.append(f"(NOT {stack.pop()})")
                elif op in ("&", "|") and len(stack) >= 2:
                    left, right = stack.pop(), stack.pop()
                    sql_op = "AND" if op == "&" else "OR"
                    stack.append(f"({left} {sql_op} {right})")
            elif isinstance(item, (tuple, list)):
                stack.append(process_leaf(item))

        where = " AND ".join(reversed(stack))
        return " ".join(joins), where, params