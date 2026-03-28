# backend/modules/mod_test/models/test_line.py
from app.core.orm import Model, Field, RelationField

class TestLine(Model):
    """
    🧪 LÍNEAS DE PRUEBA (El Detalle)
    Definición robusta para evitar errores de conversión decimal y asegurar
    la integridad referencial con el borrado en cascada.
    """
    _name = "test.line"

    # La llave foránea que apunta a la cabecera (Many2one)
    # ondelete="cascade" asegura que si borras el experimento, sus líneas mueren con él.
    record_id = RelationField(
        "test.record", 
        label="Registro Padre", 
        required=True, 
        ondelete="cascade"
    )
    
    name = Field(
        type_='string', 
        label='Descripción de la línea', 
        required=True
    )

    # 🛡️ PROTECCIÓN DECIMAL: Definimos un default de 0.0 para evitar que el 
    # driver de la base de datos reciba un string vacío ('') y lance un error.
    qty = Field(
        type_='float', 
        default=0.0, 
        label='Cantidad'
    )

    notes = Field(
        type_='string', 
        label='Notas adicionales'
    )