# backend/modules/core_base/models/res_users.py
from app.core.orm import Model, Field, RelationField, Many2manyField
from app.core.security import hash_password, verify_password, is_password_hash


class ResUsers(Model):
    """
    👤 USUARIOS DEL SISTEMA (HiperDios Core)
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
    async def create(cls, vals: dict, context=None):
        vals = dict(vals or {})

        if "login" in vals:
            vals["login"] = cls._normalize_login(vals["login"])
            if not vals["login"]:
                raise ValueError("El login no puede estar vacío.")

        if "password" in vals and vals["password"]:
            if not is_password_hash(vals["password"]):
                vals["password"] = await hash_password(vals["password"])

        # Auto-creación de partner si no viene
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

        return await super().create(vals, context=context)

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

        # Sincronización ligera con partner
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
        """
        Valida la contraseña del usuario instanciado.
        """
        if not self.active:
            raise PermissionError("Usuario desactivado.")

        if not self.password:
            raise PermissionError("Usuario sin contraseña asignada.")

        is_valid = await verify_password(password, self.password)
        if not is_valid:
            raise PermissionError("Contraseña incorrecta.")

        return True