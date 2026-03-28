# backend/app/core/scaffolder.py
import traceback
from typing import Type, List, Dict, Any
from app.core.registry import Registry
from app.core.env import Context

class ViewScaffolder:
    """
    🏗️ GENERADOR DE UI AUTOMÁTICO (Nivel HiperDios - Odoo 19 Clone)
    Transforma el ADN del Modelo y sus Mixins en una interfaz viva y funcional.
    """
    
    TYPE_MAPPING = {
        "string": "TextInput",
        "text": "TextArea",          
        "decimal": "NumberInput",
        "integer": "NumberInput",    
        "monetary": "MonetaryInput",      
        "bool": "BooleanSwitch",
        "selection": "SelectInput",
        "relation": "Many2OneLookup",   
        "many2one": "Many2OneLookup",   
        "one2many": "One2ManyLines",
        "many2many": "Many2ManyTags",
        "date": "DateInput",              
        "datetime": "DateTimeInput",          
        "password": "TextInput",     
        "binary": "FileUploader",          
        "image": "ImageUploader"            
    }

    # 🚨 AQUÍ ESTÁ LA MAGIA: 'state' NUNCA SE DIBUJARÁ COMO CAMPO EN EL FORMULARIO
    HIDDEN_FIELDS = {'id', 'create_date', 'write_date', 'create_uid', 'write_uid', 'write_version', 'parent_path', 'x_ext', 'active', 'state'}

    # 💎 ALMACÉN DIRECTO DE VISTAS (Adiós al agujero negro del Registry)
    _explicit_views = []

    @classmethod
    def register_view(cls, view_instance):
        """Recibe el plano desde el módulo y lo asegura en su propia memoria"""
        cls._explicit_views.append(view_instance)
        print(f"✅ [SDUI] Vista registrada exitosamente para: {getattr(view_instance, 'model', 'N/A')}")

    @classmethod
    async def get_default_view(cls, model_name: str, view_type: str = 'form') -> Dict[str, Any]:
        """
        🛡️ ENVOLTURA DE SEGURIDAD Y ENRUTADOR MAESTRO
        """
        try:
            # =====================================================================
            # 🚀 1. EL INTERCEPTOR DIRECTO (Nivel Enterprise)
            # =====================================================================
            for view_instance in cls._explicit_views:
                if getattr(view_instance, 'model', '') == model_name and getattr(view_instance, 'view_type', 'form') == view_type:
                    print(f"🎨 [SDUI] Sirviendo Vista Explícita para: {model_name}")
                    return view_instance.compile()

            # =====================================================================
            # ⚙️ 2. GENERADOR IMPLÍCITO (Si no hay plano manual, auto-generamos)
            # =====================================================================
            print(f"🏗️ [SDUI] Generando Vista Implícita/Hardcodeada para: {model_name}")
            return await cls._build_view(model_name, view_type)

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"\n🔥 CRASH EN SCAFFOLDER ({model_name}):\n{error_trace}")
            
            # Devolvemos una vista Atómica que dibuja el error en React
            return {
                "type": "Container",
                "props": {"layout": "col", "gap": 4, "padding": 6, "border": True},
                "children": [
                    {"type": "Typography", "props": {"content": "🔥 500 Internal Server Error (Scaffolder)", "variant": "h2", "color": "red-600"}},
                    {"type": "Typography", "props": {"content": str(e), "weight": "bold", "color": "red-800"}},
                    {"type": "TextArea", "props": {"name": "trace", "readonly": True}, "data": {"trace": error_trace}}
                ]
            }

    @classmethod
    async def _build_view(cls, model_name: str, view_type: str) -> Dict[str, Any]:
        # Extracción segura de Behaviors
        try:
            behaviors = Registry.get_behaviors(model_name)
        except AttributeError:
            behaviors = []
            
        fields_meta = Registry.get_fields_for_model(model_name)
        
        if not fields_meta:
            return {"type": "Typography", "props": {"content": f"Error: No hay metadatos para {model_name}", "color": "red-600"}}

        # Validación a prueba de balas para saber si es módulo de ventas
        is_sale = model_name in ['sale.order', 'sale_order']

        # =====================================================================
        # 💎 EXTRACCIÓN DE ACCIONES GLOBALES (FIX DEL WRAPPER)
        # =====================================================================
        model_actions = []
        model_cls = Registry.get_model(model_name)
        if model_cls:
            for attr_name in dir(model_cls):
                attr = getattr(model_cls, attr_name)
                if hasattr(attr, '_action_meta'):
                    # 🔥 EL FIX MAESTRO:
                    # Clonamos la metadata y forzamos el nombre real del método (attr_name)
                    # para evitar que el decorador de Python nos devuelva el nombre "wrapper".
                    meta = dict(attr._action_meta)
                    meta['name'] = attr_name
                    meta['method'] = attr_name
                    meta['action'] = attr_name
                    model_actions.append(meta)

        # =====================================================================
        # 🟢 1. VISTA DE LISTA (LIST VIEW)
        # =====================================================================
        if view_type == 'list':
            if is_sale:
                columns = [
                    {"field": "name", "label": "Número", "type": "TextInput"},
                    {"field": "create_date", "label": "Fecha de creación", "type": "DateInput"},
                    {"field": "partner_id", "label": "Cliente", "type": "Many2OneLookup"},
                    {"field": "user_id", "label": "Vendedor", "type": "Avatar"},
                    {"field": "activity_ids", "label": "Actividades", "type": "Activity"},
                    {"field": "company_id", "label": "Empresa", "type": "Many2OneLookup"},
                    {"field": "amount_total", "label": "Total", "type": "MonetaryInput"},
                    {"field": "state", "label": "Estado", "type": "Badge"}
                ]
            else:
                columns = []
                for f_name, f_meta in fields_meta.items():
                    if f_name in cls.HIDDEN_FIELDS:
                        continue
                    
                    meta_dict = f_meta if isinstance(f_meta, dict) else {}
                    raw_type = meta_dict.get('type', 'string')
                    
                    columns.append({
                        "field": f_name,
                        "label": meta_dict.get('label', f_name.title()),
                        "type": cls.TYPE_MAPPING.get(raw_type, "TextInput")
                    })
            
            return {
                "type": "Container",
                "props": {"layout": "col", "gap": 4, "padding": 4},
                "children": [
                    {
                        "type": "DataGrid",
                        "props": {
                            "key": f"grid_{model_name.replace('.', '_')}", 
                            "data_source": f"data_{model_name.replace('.', '_')}", 
                            "columns": columns[:8], 
                            "title": "Cotizaciones" if is_sale else f"Listado de {model_name.replace('.', ' ').title()}"
                        }
                    }
                ],
                "actions": model_actions 
            }

        # =====================================================================
        # 📝 2. VISTA DE FORMULARIO (FORM VIEW)
        # =====================================================================
        header_components = []
        body_children = []
        table_components = []
        footer_components = []

        # 💎 CABECERA (StatusBar)
        has_state = 'state' in fields_meta
        if (has_state or is_sale or 'aprobable' in behaviors) and view_type == 'form':
            if is_sale:
                statusbar_options = [['draft', 'Cotización'], ['sent', 'Cotización Enviada'], ['sale', 'Orden de Venta'], ['done', 'Bloqueado'], ['cancel', 'Cancelado']]
            else:
                statusbar_options = [['draft', 'Borrador'], ['waiting', 'En Espera'], ['approved', 'Aprobado'], ['rejected', 'Rechazado']]

            header_components.append({
                "type": "StatusBar",
                "props": {
                    "field": "state",
                    "options": statusbar_options
                }
            })

        if is_sale:
            # 🚀 DISEÑO EXACTO DE ODOO 19 PARA VENTAS (100% Protegido)
            body_children = [
                {
                    "type": "Group", 
                    "props": {}, 
                    "children": [
                        # Columna Izquierda (Cliente)
                        {"type": "Container", "props": {"layout": "col", "gap": 1}, "children": [
                            {"type": "Many2OneLookup", "props": {"name": "partner_id", "label": "Cliente", "placeholder": "Comience a escribir para encontrar a un cliente..."}},
                            {"type": "Many2OneLookup", "props": {"name": "sale_order_template_id", "label": "Plantilla de cotización"}},
                        ]},
                        # Columna Derecha (Fechas y Pagos)
                        {"type": "Container", "props": {"layout": "col", "gap": 1}, "children": [
                            {"type": "DateInput", "props": {"name": "validity_date", "label": "Vencimiento"}},
                            {"type": "Many2OneLookup", "props": {"name": "payment_term_id", "label": "Términos de pago"}},
                        ]}
                    ]
                },
                {
                    "type": "Notebook",
                    "props": {"tabs": ["Líneas de la orden", "Otra información"]},
                    "children": [
                        # PESTAÑA 1: Líneas
                        {"type": "Container", "props": {"layout": "col", "gap": 0}, "children": [
                            {"type": "One2ManyLines", "props": {"name": "order_line", "data_source": "order_line"}}
                        ]},
                        # PESTAÑA 2: Otra info
                        {"type": "Container", "props": {"layout": "grid", "gap": 8, "padding": 4}, "children": [
                            {"type": "Container", "props": {"layout": "col", "gap": 2}, "children": [
                                {"type": "Typography", "props": {"content": "Ventas", "variant": "h2", "color": "slate-800"}},
                                {"type": "Many2OneLookup", "props": {"name": "user_id", "label": "Vendedor"}},
                                {"type": "Many2OneLookup", "props": {"name": "company_id", "label": "Empresa"}},
                                {"type": "Many2ManyTags", "props": {"name": "tag_ids", "label": "Etiquetas"}},
                            ]},
                            {"type": "Container", "props": {"layout": "col", "gap": 2}, "children": [
                                {"type": "Typography", "props": {"content": "Facturación y Seguimiento", "variant": "h2", "color": "slate-800"}},
                                {"type": "TextInput", "props": {"name": "client_order_ref", "label": "Referencia del cliente"}},
                            ]}
                        ]}
                    ]
                }
            ]
        else:
            # ⚙️ GENERACIÓN AUTOMÁTICA GENÉRICA (Para contactos, productos, etc.)
            generic_fields = []
            for f_name, f_meta in fields_meta.items():
                # ✨ EL FILTRO DE SEGURIDAD ABSOLUTO
                if f_name in cls.HIDDEN_FIELDS:
                    continue
                
                meta_dict = f_meta if isinstance(f_meta, dict) else {}
                raw_type = meta_dict.get('type', 'string')
                comp_type = cls.TYPE_MAPPING.get(raw_type, "TextInput")
                comodel = meta_dict.get('comodel') or meta_dict.get('target')
                
                atom_props = {
                    "name": f_name,
                    "label": meta_dict.get('label', f_name.title()),
                    "options": meta_dict.get('options', [])
                }

                if comp_type in ["One2ManyLines", "DataGrid"]:
                    atom_props["data_source"] = f_name
                    atom_props["comodel"] = comodel 
                    
                    # MAGIA INTELIGENTE: Si el backend puede, que mande las columnas para ahorrarle trabajo a React
                    inverse = meta_dict.get('inverse_name', '')
                    atom_props["inverse_name"] = inverse
                    if comodel:
                        child_fields = Registry.get_fields_for_model(comodel)
                        if child_fields:
                            child_columns = []
                            for cf_name, cf_meta in child_fields.items():
                                if cf_name in cls.HIDDEN_FIELDS or cf_name == inverse: continue
                                c_meta = cf_meta if isinstance(cf_meta, dict) else {}
                                child_columns.append({
                                    "field": cf_name,
                                    "label": c_meta.get('label', cf_name.title()),
                                    "type": cls.TYPE_MAPPING.get(c_meta.get('type', 'string'), "TextInput")
                                })
                            atom_props["columns"] = child_columns
                            
                    table_components.append({"type": comp_type, "props": atom_props})
                elif comp_type == "Many2OneLookup":
                    atom_props["comodel"] = comodel
                    generic_fields.append({"type": comp_type, "props": atom_props})
                else:
                    generic_fields.append({"type": comp_type, "props": atom_props})

            body_children = [{"type": "Group", "props": {}, "children": generic_fields}, *table_components]

        # --- PIE DE PÁGINA ---
        if 'trazable' in behaviors and view_type == 'form':
            footer_components.append({
                "type": "Chatter",
                "props": {"res_model": model_name}
            })

        # --- 📦 ENSAMBLAJE FINAL ---
        final_children = []
        final_children.extend(header_components)
        final_children.append({
            "type": "Card",
            "props": {}, # El componente de React leerá el nombre ("SSSS") automáticamente
            "children": body_children
        })
        final_children.extend(footer_components)

        return {
            "type": "Container",
            "props": {"layout": "col", "gap": 0, "padding": 0, "border": False},
            "children": final_children,
            "actions": model_actions 
        }