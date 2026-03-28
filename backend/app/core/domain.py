# backend/app/core/domain.py
from typing import List, Tuple, Any, Dict, Union

class DomainEngine:
    """
    🧠 EL COMPILADOR DE DOMINIOS (AST to SQL - Nivel HiperDios)
    Evalúa en RAM (Fallback para UI) y Compila a SQL Crudo (WHERE + JOINs) en O(1).
    """

    @staticmethod
    def _get_nested_value(record_instance: Any, field_path: str) -> Any:
        parts = field_path.split('.')
        current_val = record_instance
        for part in parts:
            if hasattr(current_val, part):
                try: current_val = getattr(current_val, part)
                except ValueError: return None 
            else: return None
            if current_val is None: break
        return current_val

    @staticmethod
    def _evaluate_leaf(leaf: Tuple, record_data: Dict[str, Any], record_instance: Any) -> bool:
        """Evaluación en RAM (Legacy para @compute properties)"""
        if len(leaf) != 3: return False
        field, operator, value = leaf
        
        if '.' in field and record_instance:
            record_value = DomainEngine._get_nested_value(record_instance, field)
        else:
            record_value = record_data.get(field)

        if hasattr(record_value, 'id'): record_value = record_value.id

        if field == 'id' or field.endswith('_id'):
            if isinstance(record_value, str) and record_value.isdigit():
                record_value = int(record_value)
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            elif isinstance(value, (list, tuple, set)):
                value = [int(v) if isinstance(v, str) and v.isdigit() else v for v in value]

        if operator == '=': return record_value == value
        elif operator == '!=': return record_value != value
        elif operator in ('in', 'not in'):
            if not isinstance(value, (list, tuple, set)): value = [value]
            res = record_value in value
            return res if operator == 'in' else not res
        elif operator == '>': return record_value is not None and record_value > value
        elif operator == '<': return record_value is not None and record_value < value
        elif operator == '>=': return record_value is not None and record_value >= value
        elif operator == '<=': return record_value is not None and record_value <= value
        elif operator == 'ilike': 
            return bool(record_value and str(value).lower() in str(record_value).lower())
            
        return False

    @staticmethod
    def check(record_data: Dict[str, Any], domain: List[Union[str, Tuple]], record_instance=None) -> bool:
        """Fallback RAM (Se ejecuta para reglas locales o UI)"""
        if not domain: return True
        stack = []
        for item in reversed(domain):
            if isinstance(item, str):
                operator = item.upper()
                if operator == '!':
                    if stack: stack.append(not stack.pop())
                elif operator in ('&', '|'):
                    if len(stack) >= 2:
                        left = stack.pop()
                        right = stack.pop()
                        result = (left and right) if operator == '&' else (left or right)
                        stack.append(result)
            elif isinstance(item, (tuple, list)):
                result = DomainEngine._evaluate_leaf(item, record_data, record_instance)
                stack.append(result)
        return all(stack)

    # =========================================================================
    # 💎 LA SOLUCIÓN HIPERDIOS: Compilador AST a SQL
    # =========================================================================
    @staticmethod
    def compile_sql(domain: List[Union[str, Tuple]], base_model: str) -> Tuple[str, str, List[Any]]:
        """
        Transforma Notación Polaca y Rutas con puntos ('company_id.name')
        en sentencias nativas `LEFT JOIN` y `WHERE` para PostgreSQL.
        Retorna: (joins_sql, where_sql, parameters)
        """
        if not domain:
            return "", "", []

        from app.core.registry import Registry

        joins = []
        params = []
        join_map = {} 
        alias_counter = 0

        def get_alias():
            nonlocal alias_counter
            alias_counter += 1
            return f"t{alias_counter}"

        def process_leaf(leaf: Tuple) -> str:
            if len(leaf) != 3: return "TRUE"
            field_path, op, value = leaf
            
            # 1. 🧬 Resolución de Auto-JOINs (Notación por puntos)
            parts = field_path.split('.')
            current_model = base_model
            current_alias = "t0"

            for i in range(len(parts) - 1):
                rel_field = parts[i]
                fields_config = Registry.get_fields_for_model(current_model)
                meta = fields_config.get(rel_field, {})
                target_model = meta.get('target') or meta.get('relation')
                
                if not target_model:
                    raise ValueError(f"Domain Compiler Error: Relación '{rel_field}' no existe en '{current_model}'")
                
                join_key = (current_alias, rel_field)
                if join_key not in join_map:
                    new_alias = get_alias()
                    join_map[join_key] = new_alias
                    target_table = target_model.replace(".", "_")
                    joins.append(f'LEFT JOIN "{target_table}" {new_alias} ON {current_alias}."{rel_field}" = {new_alias}.id')
                
                current_alias = join_map[join_key]
                current_model = target_model

            # 2. Resolución del campo terminal
            final_field = parts[-1]
            fields_config = Registry.get_fields_for_model(current_model)
            
            sql_op = op.upper()
            if sql_op == '=?': sql_op = 'ILIKE'

            is_native = final_field in fields_config or final_field == 'id'
            f_type = fields_config.get(final_field, {}).get('type') if final_field != 'id' else 'integer'

            # 3. Limpieza de Tipos Segura
            if f_type in ['relation', 'many2one', 'integer'] or final_field == 'id':
                if isinstance(value, (list, tuple, set)):
                    value = [int(x) for x in value if str(x).isdigit()]
                    if not value: return "FALSE" # Lista vacía en un IN genera falso instantáneo
                elif isinstance(value, str) and value.isdigit():
                    value = int(value)
                elif isinstance(value, str) and not value.isdigit() and op not in ['ilike', 'not ilike']:
                    return "FALSE" # Bloqueo anti-crash: Intentaron igualar un texto a un BIGSERIAL

            params.append(value)
            param_idx = len(params)

            # 4. Construcción del SQL Crudo
            if is_native:
                field_ref = f'{current_alias}."{final_field}"'
                cast_type = "bigint[]" if f_type in ['relation', 'many2one', 'integer'] or final_field == 'id' else "text[]"
                
                if sql_op in ('IN', 'NOT IN'):
                    if not isinstance(value, (list, tuple, set)): params[-1] = [value]
                    op_str = "= ANY" if sql_op == 'IN' else "!= ALL"
                    return f"{field_ref} {op_str}(${param_idx}::{cast_type})"
                else:
                    return f"{field_ref} {sql_op} ${param_idx}"
            else:
                # Inyección JSONB
                field_ref = f"{current_alias}.x_ext->>'{final_field}'"
                params[-1] = str(value) 
                return f"{field_ref} {sql_op} ${param_idx}"

        # 5. Máquina de Pila (Algoritmo de Prioridad Inversa)
        stack = []
        for item in reversed(domain):
            if isinstance(item, str):
                operator = item.upper()
                if operator == '!':
                    if stack: stack.append(f"(NOT {stack.pop()})")
                elif operator in ('&', '|'):
                    if len(stack) >= 2:
                        left = stack.pop()
                        right = stack.pop()
                        sql_log_op = "AND" if operator == '&' else "OR"
                        stack.append(f"({left} {sql_log_op} {right})")
            elif isinstance(item, (tuple, list)):
                stack.append(process_leaf(item))

        # Los dominios Odoo tienen un 'AND' implícito para los remanentes de la pila
        where_clause = " AND ".join(reversed(stack))
        joins_clause = " ".join(joins)

        return joins_clause, where_clause, params