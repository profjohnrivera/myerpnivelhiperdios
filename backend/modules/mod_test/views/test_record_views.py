# backend/modules/mod_test/views/test_record_views.py
from app.core.sdui import (
    Component, Container, HeaderBar, StatusBar, Card, Group, 
    TextInput, TextArea, BooleanSwitch, Notebook, One2ManyLines, ModelActions,
    NumberInput, MonetaryInput, DateInput, DateTimeInput, SelectInput,
    Many2OneLookup, Many2ManyTags, FileUploader, ImageUploader
)

class TestRecordFormView(Component):
    """🎨 VISTA EXPLÍCITA PARA EL LABORATORIO (Master Template 100 Años)"""
    def __init__(self):
        self.id = "test.record.form"
        self.model = "test.record"   
        self.view_type = "form"
    
    def compile(self) -> dict:
        view_ast = Container(layout="col", gap=0, padding=0, border=False, children=[
            # 1. CABECERA (Botones y Estado)
            HeaderBar(children=[
                ModelActions("test.record"), 
                StatusBar(field="status", options=[['draft', 'Borrador'], ['done', 'Completado']])
            ]),
            
            # 2. CUERPO PRINCIPAL
            Card(children=[
                # Avatar arriba a la izquierda como en Odoo
                Container(layout="row", gap=4, padding=0, children=[
                    ImageUploader(name="image_1920", label=""),
                    Container(layout="col", gap=1, padding=0, children=[
                        TextInput(name="name", label="Nombre del Experimento"),
                        SelectInput(name="priority", label="Nivel de Prioridad", options=[['low', 'Baja'], ['normal', 'Normal'], ['high', 'Alta']])
                    ])
                ]),
                
                # Campos principales divididos
                Group(columns=2, children=[
                    # Columna Izquierda
                    Container(layout="col", gap=1, padding=0, children=[
                        Many2OneLookup(name="user_id", label="Usuario Responsable", comodel="res.users"),
                        BooleanSwitch(name="is_active", label="Activar Experimento"),
                        Many2ManyTags(name="tag_ids", label="Etiquetas de Clasificación", comodel="test.tag")
                        
                    ]),
                    # Columna Derecha
                    Container(layout="col", gap=1, padding=0, children=[
                        DateInput(name="start_date", label="Fecha de Inicio"),
                        DateTimeInput(name="end_datetime", label="Fecha y Hora de Cierre"),
                    ])
                ]),
                
                # 3. PESTAÑAS MAESTRAS
                Notebook(tabs=["Reactivos (One2Many)", "Tipos Numéricos", "Archivos y Textos"], children=[
                    
                    # PESTAÑA 1: Tabla Relacional
                    Container(layout="col", gap=0, padding=0, children=[
                        One2ManyLines(
                            name="line_ids", 
                            data_source="line_ids", 
                            comodel="test.line",
                            inverse_name="record_id",
                            columns=[
                                {"field": "name", "label": "Descripción", "type": "TextInput"},
                                {"field": "qty", "label": "Cantidad", "type": "NumberInput"},
                                {"field": "notes", "label": "Notas Adicionales", "type": "TextInput"}
                            ]
                        )
                    ]),
                    
                    # PESTAÑA 2: Demostración de Matemáticas
                    Container(layout="col", gap=4, padding=4, children=[
                        Group(columns=2, children=[
                            Container(layout="col", gap=1, padding=0, children=[
                                NumberInput(name="test_integer", label="Número de Ciclos (Entero)"),
                                NumberInput(name="test_float", label="Margen de Error (Decimal)"),
                            ]),
                            Container(layout="col", gap=1, padding=0, children=[
                                MonetaryInput(name="test_money", label="Presupuesto Asignado"),
                            ])
                        ])
                    ]),

                    # PESTAÑA 3: Documentos y Descripciones largas
                    Container(layout="col", gap=4, padding=4, children=[
                        FileUploader(name="document", label="Subir PDF o Documento Anexo"),
                        TextArea(name="description", label="Bitácora de Resultados (Texto Largo)"),
                    ])
                ])
            ])
        ]).to_json()
        
        view_ast['id'] = self.id
        return view_ast