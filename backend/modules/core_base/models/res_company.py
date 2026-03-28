# backend/modules/core_base/models/res_company.py
from app.core.orm import Model, Field, RelationField

class ResCompany(Model):
    """
    🏢 LA EMPRESA (res.company)
    Define la entidad legal dueña de los datos.
    """
    _rec_name = "name"

    name = Field(type_='string', label='Nombre Legal', required=True)
    vat = Field(type_='string', label='RUC/NIT/NIF')
    currency_id = Field(type_='string', label='Moneda base', default='PEN') # Soles por defecto
    partner_id = RelationField("ResPartner", label="Contacto de Empresa")