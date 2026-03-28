# backend/modules/core_base/models/res_company.py
from app.core.orm import Model, Field, RelationField


class ResCompany(Model):
    """
    🏢 LA EMPRESA (res.company)
    Define la entidad legal dueña de los datos.
    """
    _name = "res.company"
    _description = "Compañía"
    _rec_name = "name"

    _sql_constraints = [
        ("res_company_name_unique", 'UNIQUE("name")', "El nombre de la compañía debe ser único."),
    ]

    name = Field(type_="string", label="Nombre Legal", required=True, index=True)
    vat = Field(type_="string", label="RUC/NIT/NIF")
    currency_id = Field(type_="string", label="Moneda base", default="PEN")
    partner_id = RelationField("res.partner", label="Contacto de Empresa")
    active = Field(type_="bool", default=True, label="Activo")