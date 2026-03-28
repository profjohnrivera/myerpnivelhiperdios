# modules/core_system/views.py
from app.core.sdui import Card, Form, TextInput, Badge, Button, Tabs, Tab

def sequence_detail(id):
    return Card(
        title='Gestión de Sequence',
        children=[
            Tabs(children=[
                Tab(label="General", children=[
                    Form(children=[
                TextInput(key="name", label="Referencia/Nombre"),
                Badge(key="active", label="Activo", color="green"),
                Badge(key="state", label="Estado", color="blue"),
                TextInput(key="newcampo3", label="Newcampo3"),
                        Button(label="Confirmar", action="action_confirm", variant="primary")
                    ])
                ]),
                Tab(label="Auditoría", children=[
                    Form(children=[
                        TextInput(key="create_date", label="Creado el", type="date"),
                        TextInput(key="create_uid", label="Creado por"),
                        TextInput(key="write_date", label="Editado el", type="date"),
                        TextInput(key="write_uid", label="Editado por"),
                    ])
                ])
            ])
        ]
    )
