# backend/modules/mod_test/models/test_record.py
from app.core.orm import Model, Field, SelectionField, One2manyField, RelationField, check_state
from app.core.decorators import action

class TestRecord(Model):
    _name = "test.record"
    _rec_name = "name"

    # 1. Textos y Básicos
    name = Field(type_='string', label='Nombre del Experimento', required=True)
    description = Field(type_='text', label='Descripción detallada')
    is_active = Field(type_='bool', default=True, label='Está Activo')
    
    tag_ids = Field(type_='jsonb', label='Etiquetas de Clasificación')

    # 2. Selectores y Estados
    status = SelectionField(options=[('draft', 'Borrador'), ('done', 'Completado')], default='draft', label='Estado')
    priority = SelectionField(options=[('low', 'Baja'), ('normal', 'Normal'), ('high', 'Alta')], default='normal', label='Prioridad')

    # 3. Fechas
    start_date = Field(type_='date', label='Fecha de Inicio')
    end_datetime = Field(type_='datetime', label='Fecha y Hora de Fin')

    # 4. Números
    test_integer = Field(type_='integer', label='Número Entero')
    test_float = Field(type_='float', label='Número Decimal')
    test_money = Field(type_='monetary', label='Monto Monetario')

    # 5. Archivos (Tipos binarios)
    document = Field(type_='binary', label='Documento Adjunto')
    image_1920 = Field(type_='image', label='Imagen Principal')

    # 6. Relaciones
    user_id = RelationField("res.users", label="Responsable")
    line_ids = One2manyField("test.line", inverse_name="record_id", label="Líneas de Prueba")

    # =========================================================================
    # ⚡ ACCIONES DE NEGOCIO (Lógica SDUI)
    # =========================================================================
    @action(label="Confirmar", icon="check", variant="primary")
    @check_state(['draft'])
    async def action_confirm(self):
        """Transición de estado dictada por el backend."""
        print(f"⚡ [LABORATORIO] Confirmando experimento: {self.name}")
        await self.write({'status': 'done'})