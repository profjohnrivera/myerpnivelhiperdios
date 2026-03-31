# backend/modules/mod_test/models/test_advanced_record.py

from app.core.orm import Model, Field, RelationField, SelectionField
from app.core.orm.fields import HtmlField, JsonField, RelatedField, ReferenceField


class TestAdvancedRecord(Model):
    """
    Smoke model para la nueva ola de campos.
    """
    _name = "test.advanced.record"
    _rec_name = "name"

    name = Field(type_="string", label="Nombre", required=True)

    state = SelectionField(
        options=[("draft", "Borrador"), ("done", "Completado")],
        default="draft",
        label="Estado",
    )

    user_id = RelationField("res.users", label="Responsable")
    partner_id = RelationField("res.partner", label="Contacto")

    html_content = HtmlField(label="Contenido HTML")
    payload_json = JsonField(label="Payload JSON", default=dict)

    reference_target = ReferenceField(
        label="Referencia Global",
        allowed_models=["res.partner", "res.company", "product.product"],
    )

    user_login = RelatedField(
        "user_id.login",
        field_type="string",
        label="Login del Responsable",
        readonly=True,
        store=False,
    )

    user_company_id = RelatedField(
        "user_id.company_id",
        field_type="many2one",
        target_model="res.company",
        label="Compañía del Responsable",
        readonly=True,
        store=False,
    )

    partner_email = RelatedField(
        "partner_id.email",
        field_type="string",
        label="Email del Contacto",
        readonly=True,
        store=False,
    )