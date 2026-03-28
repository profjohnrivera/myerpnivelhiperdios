# backend/modules/core_base/models/res_partner.py
from app.core.orm import Model, Field, SelectionField

class ResPartner(Model):
    """
    👥 MAESTRO DE CONTACTOS
    Identidad física y legal. Soporta localización y tipos de dirección.
    """
    _rec_name = "name"

    name = Field(type_='string', label='Nombre Completo', required=True)
    email = Field(type_='string', label='Email')
    vat = Field(type_='string', label='NIF/RUC/DNI')
    is_company = Field(type_='bool', label='Es Compañía', default=False)
    
    # Estándares Enterprise
    lang = Field(type_='string', default='es_ES', label='Idioma')
    tz = Field(type_='string', default='UTC', label='Zona Horaria')
    
    type = SelectionField(
        options=['contact', 'invoice', 'delivery', 'other'], 
        default='contact', 
        label='Tipo de Dirección'
    )