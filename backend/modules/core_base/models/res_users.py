# backend/modules/core_base/models/res_users.py

from app.core.orm import Model, Field, RelationField, Many2manyField
from app.core.security import hash_password, verify_password, is_password_hash


class ResUsers(Model):
    """
    👤 USUARIOS DEL SISTEMA (HiperDios Core)
    Inspirado en el patrón de Odoo:
    - usuario vinculado a partner
    - grupos many2many
    - login normalizado
    - password siempre hasheado
    """
    _name = "res.users"
    _rec_name = "name"

    _sql_constraints = [
        ("res_users_login_unique", 'UNIQUE("login")', "El login debe ser único."),
    ]

    partner_id = RelationField("res.partner", label="Contacto Asociado")
    company_id = RelationField("res.company", label="Compañía Principal")

    name = Field(type_="string", label="Nombre Completo", required=True)
    login = Field(type_="string", label="Login / Usuario", required=True, index=True)
    password = Field(type_="string", label="Password Hash")
    active = Field(type_="bool", default=True, label="Activo")

    group_ids = Many2manyField("res.groups", label="Roles / Grupos")

    @staticmethod
    def _normalize_login(login: str) -> str:
        return (login or "").strip().lower()

    @classmethod
    async def _prepare_create_vals(cls, vals: dict, context=None) -> dict:
        vals = dict(vals or {})

        if "login" in vals:
            vals["login"] = cls._normalize_login(vals["login"])
            if not vals["login"]:
                raise ValueError("El login no puede estar vacío.")

        if "password" in vals and vals["password"]:
            if not is_password_hash(vals["password"]):
                vals["password"] = await hash_password(vals["password"])

        if not vals.get("partner_id"):
            from app.core.env import Context

            env = Context.get_env()
            if env:
                Partner = env["res.partner"]
                partner_vals = {
                    "name": vals.get("name") or vals.get("login") or "Usuario",
                }
                if vals.get("company_id"):
                    partner_vals["company_id"] = vals["company_id"]

                partner = await Partner.create(partner_vals, context=context)
                vals["partner_id"] = partner.id

        return vals

    @classmethod
    async def _get_default_group_id(cls) -> int | None:
        """
        Devuelve el ID del grupo "Ventas / Usuario" (grupo base de todos los usuarios).
        Equivalente al base.group_user de Odoo — todo usuario autenticado pertenece a él.
        Esto garantiza que:
          1. Los ACL de negocio (product.product, sale.order, res.partner) apliquen.
          2. Las reglas RLS (ir.rule) filtren los datos correctamente.
          3. Los menús con group_ids se muestren al usuario.
        """
        try:
            from app.core.registry import Registry
            from app.core.env import Context
            env = Context.get_env()
            if not env:
                return None
            ResGroups = Registry.get_model("res.groups")
            if not ResGroups:
                return None
            groups = await ResGroups.search([("name", "=", "Ventas / Usuario")], limit=1)
            if groups:
                return groups[0].id
        except Exception:
            pass
        return None

    @classmethod
    async def create(cls, vals: dict, context=None):
        vals = await cls._prepare_create_vals(vals, context=context)
        record = await super().create(vals, context=context)

        # AUTO-ASIGNACIÓN DE GRUPO BASE (como base.group_user en Odoo)
        # Todo usuario recibe el grupo "Ventas / Usuario" automáticamente al crearse.
        # Esto garantiza ACL + RLS correctos desde el primer login.
        # Los admins también lo reciben (tienen bypass por is_system_admin=True).
        try:
            default_group_id = await cls._get_default_group_id()
            if default_group_id:
                current_groups = getattr(record, "group_ids", None)
                if current_groups is None:
                    current_groups = []
                try:
                    current_groups = list(current_groups)
                except Exception:
                    current_groups = []

                group_ids_normalized = []
                for g in current_groups:
                    if isinstance(g, (int, float)):
                        group_ids_normalized.append(int(g))
                    elif hasattr(g, "id"):
                        group_ids_normalized.append(int(g.id))

                if default_group_id not in group_ids_normalized:
                    await record.write({"group_ids": group_ids_normalized + [default_group_id]})
        except Exception:
            pass  # Nunca bloquear la creación de usuario por fallo de grupo

        return record

    async def write(self, vals: dict):
        vals = dict(vals or {})

        if "login" in vals:
            vals["login"] = self._normalize_login(vals["login"])
            if not vals["login"]:
                raise ValueError("El login no puede estar vacío.")

        if "password" in vals and vals["password"]:
            if not is_password_hash(vals["password"]):
                vals["password"] = await hash_password(vals["password"])

        result = await super().write(vals)

        try:
            if self.partner_id:
                partner_updates = {}
                if "name" in vals:
                    partner_updates["name"] = vals["name"]
                if "company_id" in vals:
                    partner_updates["company_id"] = vals["company_id"]

                if partner_updates:
                    await self.partner_id.write(partner_updates)
        except Exception:
            pass

        return result

    async def _check_credentials(self, password: str) -> bool:
        if not self.active:
            raise PermissionError("Usuario desactivado.")

        if not self.password:
            raise PermissionError("Usuario sin contraseña asignada.")

        is_valid = await verify_password(password, self.password)
        if not is_valid:
            raise PermissionError("Contraseña incorrecta.")

        return True