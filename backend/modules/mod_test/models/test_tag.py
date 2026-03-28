# backend/modules/mod_test/models/test_tag.py
from app.core.orm import Model, Field

class TestTag(Model):
    """🏷️ Modelo Maestro para Etiquetas (Many2Many)"""
    _name = "test.tag"
    _rec_name = "name"

    name = Field(type_='string', label='Nombre de la Etiqueta', required=True)
    color = Field(type_='integer', label='Índice de Color', default=0)