# backend/manage.py
import os
import sys
import ast
import datetime
import time
import shutil
import platform
import asyncio
from typing import Dict, List, Any

# --- 🔌 INFRAESTRUCTURA CORE ---
try:
    from app.core.database import engine, Base
    from sqlalchemy import text
    INFRA_READY = True
except ImportError:
    INFRA_READY = False

# --- 🎨 ESTILO HIPERDIOS (Cyberpunk Neon) ---
class C:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text, color=C.HEADER):
    print(f"\n{color}{C.BOLD}╔{'═'*70}╗{C.END}")
    print(f"{color}{C.BOLD}║ {text.center(68)} ║{C.END}")
    print(f"{color}{C.BOLD}╚{'═'*70}╝{C.END}")

# --- 🧠 MOTOR DE INTELIGENCIA (EL ORÁCULO) ---

def get_sys_info():
    """Diagnóstico en tiempo real del entorno."""
    return {
        "os": platform.system(),
        "py": sys.version.split()[0],
        "db": f"{C.GREEN}ONLINE{C.END}" if INFRA_READY else f"{C.RED}OFFLINE{C.END}",
        "ts": datetime.datetime.now().strftime("%H:%M:%S")
    }

def get_project_stats():
    """Escanea el disco para contar módulos y modelos."""
    mod_count, model_count = 0, 0
    path = "modules"
    if os.path.exists(path):
        for root, _, files in os.walk(path):
            if "module.py" in files: mod_count += 1
            if "models.py" in files:
                try:
                    with open(os.path.join(root, "models.py"), "r", encoding="utf-8") as f:
                        content = f.read()
                        model_count += len(re.findall(r"class \w+\(Model\):", content))
                except: pass
    return mod_count, model_count

def get_module_inventory() -> List[Dict]:
    """Escanea la arquitectura y califica la calidad del código."""
    inventory = []
    path = "modules"
    if not os.path.exists(path): return []
    
    for d in sorted(os.listdir(path)):
        p = os.path.join(path, d)
        if os.path.isdir(p) and not d.startswith("__"):
            # Los 7 Pilares de la Arquitectura HiperDios
            files = ["module.py", "models.py", "policies.py", "views.py", "events.py", "handlers.py", "__init__.py"]
            found = sum([os.path.exists(os.path.join(p, f)) for f in files])
            has_tests = os.path.exists(os.path.join(p, "tests"))
            
            # Score Algorithm: (Archivos + Tests) / Total * 100
            score = int(((found + (1 if has_tests else 0)) / 8) * 100)
            
            inventory.append({
                "id": d, "score": score,
                "components": {f: os.path.exists(os.path.join(p, f)) for f in files},
                "tests": has_tests
            })
    return inventory

def scan_existing_models():
    """Introspección de código para sugerencias inteligentes."""
    models_map = {}
    if not os.path.exists("modules"): return {}
    for root, _, files in os.walk("modules"):
        if "models.py" in files:
            try:
                with open(os.path.join(root, "models.py"), "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and any(b.id == 'Model' for b in node.bases if isinstance(b, ast.Name)):
                        parts = root.split(os.sep)
                        mod_name = parts[parts.index("modules")+1]
                        models_map[node.name] = f"modules.{mod_name}.models"
            except: pass
    return models_map

# --- 📋 COMANDOS DE VISUALIZACIÓN ---

def cmd_list_modules():
    print_header("TABLERO DE MANDO: INVENTARIO DE MÓDULOS", C.CYAN)
    data = get_module_inventory()
    if not data: return print(f"  {C.YELLOW}⚠ No hay módulos instalados.{C.END}")

    print(f"{C.BOLD}{'MÓDULO':<20} | {'SCORE':<6} | {'COMPONENTS':<35} | {'TEST':<4}{C.END}")
    print("-" * 80)
    for m in data:
        s = m['score']
        c = C.GREEN if s == 100 else (C.YELLOW if s >= 50 else C.RED)
        comps = "".join([f"{C.GREEN}•{C.END}" if v else f"{C.RED}·{C.END}" for k,v in m['components'].items()])
        print(f"{m['id']:<20} | {c}{s:>3}%{C.END}   | {comps:<35} | {'✅' if m['tests'] else '❌'}")

async def cmd_health_check():
    print_header("SISTEMA DE DIAGNÓSTICO INTEGRAL", C.YELLOW)
    info = get_sys_info()
    print(f"  🖥️  KERNEL: {info['os']} | PY: {info['py']} | TIME: {info['ts']}")
    
    if INFRA_READY:
        try:
            start = time.time()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            status = f"{C.GREEN}OPTIMAL{C.END}" if latency < 10 else f"{C.YELLOW}SLOW{C.END}"
            print(f"  🗄️  DB CONNECT: {info['db']} ({latency:.2f}ms) -> {status}")
        except Exception as e:
            print(f"  🗄️  DB CONNECT: {C.RED}CRITICAL FAILURE{C.END} -> {e}")

# --- 🧹 MANTENIMIENTO ---
def cmd_cleanup():
    print(f"{C.YELLOW}Limpiando artefactos de compilación...{C.END}")
    n = 0
    for r, d, _ in os.walk("."):
        for c in [x for x in d if x == "__pycache__"]:
            shutil.rmtree(os.path.join(r, c))
            n += 1
    print(f"{C.GREEN}✔ Sistema purgado ({n} nodos eliminados).{C.END}")

# --- 🧙 WIZARD 20.0: THE OMNISCIENT ARCHITECT ---

def get_selection(opts, prompt="Seleccione:"):
    print(f"\n{C.CYAN}{prompt}{C.END}")
    for i, o in enumerate(opts, 1): print(f"   {C.BOLD}{i}.{C.END} {o.get('label') or o.get('l')}")
    while True:
        try:
            choice = int(input(f"{C.YELLOW}   >> {C.END}")) - 1
            if 0 <= choice < len(opts): return opts[choice].get('value') or opts[choice].get('v')
        except: pass
        print(f"{C.RED}❌ Error.{C.END}")

def wizard():
    print_header("ARCHITECT WIZARD: GENERADOR DE CÓDIGO MAESTRO")
    known_models = scan_existing_models()
    
    mod_id = input(f"{C.BOLD}ID del Módulo (ej: mod_logistics): {C.END}").strip()
    if not mod_id: return
    res_name = input(f"{C.BOLD}Recurso Principal (ej: Shipment): {C.END}").strip()
    
    # --- Inteligencia de Negocio ---
    has_workflow = input(f"{C.CYAN}¿Tiene Flujo de Estados (Borrador -> Hecho)? (y/N): {C.END}").lower() == 'y'
    has_multitenant = input(f"{C.CYAN}¿Es Privado por Usuario (Multitenant)? (y/N): {C.END}").lower() == 'y'
    
    icons = [{'v': 'box', 'l': 'Inventario'}, {'v': 'dollar-sign', 'l': 'Ventas/Fin'}, {'v': 'users', 'l': 'RRHH'}, {'v': 'settings', 'l': 'Config'}]
    mod_icon = get_selection(icons, "Icono del Módulo:")

    # --- CAMPOS DE AUDITORÍA (OBLIGATORIOS NIVEL DIOS) ---
    fields = [
        {"name": "name", "type": "string", "label": "Referencia/Nombre", "std": True},
        {"name": "active", "type": "bool", "label": "Activo", "std": True, "def": "True"},
        {"name": "create_date", "type": "datetime", "label": "Creado el", "std": True},
        {"name": "create_uid", "type": "rel", "target": "User", "label": "Creado por", "std": True},
        {"name": "write_date", "type": "datetime", "label": "Editado el", "std": True},
        {"name": "write_uid", "type": "rel", "target": "User", "label": "Editado por", "std": True},
    ]
    
    if has_workflow:
        fields.append({"name": "state", "type": "selection", "opts": "draft,confirmed,done,cancelled", "label": "Estado", "std": True})
    
    if has_multitenant:
        fields.append({"name": "company_id", "type": "int", "label": "ID Compañía", "std": True})

    print(f"\n{C.CYAN}--- Diseño del Modelo de Datos ---{C.END}")
    while True:
        f_name = input(f"📝 Nuevo Campo (Enter para terminar): ").strip().lower()
        if not f_name: break
        
        # Lista completa de tipos soportados por el ORM HiperDios
        types = [
            {'v': 'string', 'l': 'Texto Corto (Char)'}, {'v': 'text', 'l': 'Texto Largo'},
            {'v': 'int', 'l': 'Entero'}, {'v': 'float', 'l': 'Moneda/Decimal'},
            {'v': 'bool', 'l': 'Booleano'}, {'v': 'date', 'l': 'Fecha'},
            {'v': 'rel', 'l': 'Relación (Many2One)'}, {'v': 'selection', 'l': 'Selección'},
            {'v': 'vector', 'l': '🤖 IA Vector'}, {'v': 'encrypted', 'l': '🔒 Encriptado'}
        ]
        f_type = get_selection(types, f"Tipo para '{f_name}':")
        f_data = {"name": f_name, "type": f_type, "label": f_name.replace("_", " ").title(), "std": False}
        
        if f_type == 'rel':
            f_data['target'] = input(f"   🔗 Modelo destino: ").strip() or "Model"
        elif f_type == 'selection':
            f_data['opts'] = input(f"   📋 Opciones (ej: a,b,c): ").strip()
            
        fields.append(f_data)

    generate_architecture(mod_id, res_name, fields, mod_icon, has_workflow, has_multitenant, known_models)

def generate_architecture(mod_id, res_name, fields, mod_icon, has_workflow, has_multitenant, known_models):
    path = os.path.join("modules", mod_id)
    if os.path.exists(path):
        if input(f"{C.RED}⚠️  El módulo existe. ¿Sobrescribir? (s/N): {C.END}").lower() != 's': return
        shutil.rmtree(path)
    os.makedirs(os.path.join(path, "tests"), exist_ok=True)

    res_cls = "".join(x.capitalize() for x in res_name.split("_"))
    res_snk = res_name.lower()
    mod_cls = "".join(x.capitalize() for x in mod_id.replace("mod_", "").split("_")) + "Module"

    # --- 1. Generador de Modelos (ORM) ---
    model_lines = []
    orm_imports = {"Model", "Field"}
    extra_imports = []
    
    if any(f.get('target') == 'User' for f in fields) and "User" in known_models:
        extra_imports.append(f"from {known_models['User']} import User")

    for f in fields:
        ftype, fname, flabel = f['type'], f['name'], f['label']
        
        if ftype == 'rel':
            orm_imports.add("RelationField")
            target = f.get('target', 'Model')
            if target not in ['User', 'Model'] and target in known_models:
                 extra_imports.append(f"from {known_models[target]} import {target}")
            model_lines.append(f"    {fname} = RelationField({target}, label='{flabel}')")
        elif ftype == 'selection':
            orm_imports.add("SelectionField")
            opts = f.get('opts', 'draft,done').split(',')
            model_lines.append(f"    {fname} = SelectionField(options={opts}, default='{opts[0].strip()}', label='{flabel}')")
        elif ftype == 'vector':
            orm_imports.add("VectorField")
            model_lines.append(f"    {fname} = VectorField(dim=1536, label='{flabel}')")
        else:
            default = f.get('def', 'None')
            model_lines.append(f"    {fname} = Field(type_='{ftype}', label='{flabel}', default={default})")

    # --- 2. Generador de Vistas (SDUI) ---
    view_lines = []
    audit_lines = [] # Pestaña secundaria
    
    for f in fields:
        fname, flabel = f['name'], f['label']
        is_audit = f.get('std') and fname not in ['name', 'state', 'active']
        
        # Selección de Widget Inteligente
        if f['type'] == 'bool': widget = f'Badge(key="{fname}", label="{flabel}", color="green")'
        elif f['type'] == 'selection': widget = f'Badge(key="{fname}", label="{flabel}", color="blue")'
        elif f['type'] == 'date' or f['type'] == 'datetime': widget = f'TextInput(key="{fname}", label="{flabel}", type="date")'
        else: widget = f'TextInput(key="{fname}", label="{flabel}")'
        
        if is_audit: audit_lines.append(f'                        {widget},')
        else: view_lines.append(f'                {widget},')

    # --- 3. Generación de Archivos con Cabeceras y Lógica Completa ---
    
    files = {
        "models.py": f"""# modules/{mod_id}/models.py
from app.core.orm import {', '.join(sorted(orm_imports))}
from app.core.decorators import action
{chr(10).join(extra_imports)}

class {res_cls}(Model):
    \"\"\"
    Modelo de Negocio: {res_cls}
    Sistema: HiperDios ERP v1.0
    \"\"\"
{chr(10).join(model_lines)}

    {f'''@action(label='Confirmar', icon='check', variant='success')
    def action_confirm(self):
        self.state = 'confirmed'
    ''' if has_workflow else ''}
""",

        "policies.py": f"""# modules/{mod_id}/policies.py
from app.core.policies import Policy
from typing import Dict, Any

class {res_cls}Access(Policy):
    \"\"\"
    🛡️ MOTOR DE SEGURIDAD RBAC
    - Nivel 1: Superadmin (Acceso Total)
    - Nivel 2: Managers (Escritura Global)
    - Nivel 3: Usuarios (Solo Propiedad)
    \"\"\"
    def evaluate(self, inputs: Dict[str, Any], mode='read') -> bool:
        # 1. Superusuario
        if inputs.get('is_admin'): return True

        # 2. Control de Lectura
        if mode == 'read':
            return self._check_read(inputs)

        # 3. Control de Escritura/Borrado
        if mode in ['write', 'unlink']:
            return self._check_write(inputs)
        
        return True # Create permitido por defecto

    def _check_read(self, inputs):
        # Visibilidad básica (Soft Delete Check)
        return inputs.get(f'data:{res_snk}:{{inputs.get("id")}}:active', True)

    def _check_write(self, inputs):
        # A. Bloqueo de Estado (State Locking)
        state = inputs.get(f'data:{res_snk}:{{inputs.get("id")}}:state')
        if state in ['confirmed', 'done', 'cancel']: 
            return False # Registro inmutable
            
        # B. Verificación de Grupo/Propiedad
        is_manager = 'group_manager' in inputs.get('groups', [])
        if is_manager: return True
        
        {f'''# Multitenancy: Solo el dueño edita
        current_user = inputs.get('current_user_id')
        owner = inputs.get(f'data:{res_snk}:{{inputs.get("id")}}:create_uid')
        return current_user == owner''' if has_multitenant else 'return True'}

    def can_trigger_action(self, inputs, action):
        return self._check_write(inputs)
""",

        "views.py": f"""# modules/{mod_id}/views.py
from app.core.sdui import Card, Form, TextInput, Badge, Button, Tabs, Tab

def {res_snk}_detail(id):
    return Card(
        title='Gestión de {res_cls}',
        children=[
            Tabs(children=[
                Tab(label="General", children=[
                    Form(children=[
{chr(10).join(view_lines)}
                        {f'Button(label="Confirmar", action="action_confirm", variant="primary")' if has_workflow else ''}
                    ])
                ]),
                Tab(label="Auditoría", children=[
                    Form(children=[
{chr(10).join(audit_lines)}
                    ])
                ])
            ])
        ]
    )
""",

        "module.py": f"""# modules/{mod_id}/module.py
from app.core.module import Module
from .models import {res_cls}
from .handlers import on_{res_snk}_created
from .events import {res_cls}Created

class {mod_cls}(Module):
    name = '{mod_id}'
    
    def register(self):
        self.bus.publish_meta(module='{mod_id}', icon='{mod_icon}', label='{res_cls}')
    
    def boot(self):
        self.bus.subscribe({res_cls}Created, on_{res_snk}_created)
        print(f'🚀 [MODULE] {{self.name}} cargado correctamente.')
""",

        "events.py": f"""# modules/{mod_id}/events.py
from app.core.events import Event

class {res_cls}Created(Event):
    \"\"\"Evento disparado tras la creación exitosa de un registro.\"\"\"
    def __init__(self, record_id): 
        self.record_id = record_id
""",

        "handlers.py": f"""# modules/{mod_id}/handlers.py
import logging
from .events import {res_cls}Created

logger = logging.getLogger(__name__)

async def on_{res_snk}_created(event: {res_cls}Created):
    \"\"\"
    Handler Asíncrono: Reacciona a la creación del registro.
    Ideal para: Enviar correos, actualizar contadores, notificaciones push.
    \"\"\"
    try:
        logger.info(f"✨ Nuevo {res_cls} detectado: {{event.record_id}}")
        # TODO: Implementar lógica de negocio (ej: Email de bienvenida)
        # service.send_email(event.record_id)
    except Exception as e:
        logger.error(f"❌ Error en handler on_{res_snk}_created: {{e}}")
""",

        "__init__.py": f"# modules/{mod_id}/__init__.py\nfrom .module import {mod_cls}\n",
        
        "tests/test_logic.py": f"""# modules/{mod_id}/tests/test_logic.py
import unittest
from ..models import {res_cls}

class Test{res_cls}(unittest.TestCase):
    def test_lifecycle(self):
        \"\"\"Prueba el ciclo de vida básico del documento.\"\"\"
        obj = {res_cls}(_id='test_1')
        self.assertTrue(obj.active, "El registro debe nacer activo")
        {'self.assertEqual(obj.state, "draft", "El estado inicial debe ser borrador")' if has_workflow else ''}
"""
    }

    for n, c in files.items():
        with open(os.path.join(path, n), "w", encoding="utf-8") as f: f.write(c.strip() + "\n")
    print(f"\n{C.GREEN}✅ Módulo '{mod_id}' generado con arquitectura de grado militar.{C.END}")

# --- 🎮 PUNTO DE ENTRADA ---

def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        info, (mods, mdls) = get_sys_info(), get_project_stats()
        print_header("KERNEL COMMAND CENTER v20.0", C.GREEN)
        print(f"  🖥️  HOST: {info['os']} | 🐍 PY: {info['py']} | 🗄️  DB: {info['db']}")
        print(f"  📊 STATS: {mods} Modules | {mdls} Models Active")
        
        opt = get_selection([
            {'v': 'run', 'l': '🚀 Iniciar Servidor (Main App)'},
            {'v': 'wizard', 'l': '✨ Crear Módulo (Hyper Scaffolding)'},
            {'v': 'list', 'l': '📋 Inventario & Salud (Quality Score)'},
            {'v': 'health', 'l': '🏥 Diagnóstico de Infraestructura'},
            {'v': 'db', 'l': '🗄️  Gestión de Base de Datos (Reset)'},
            {'v': 'test', 'l': '🧪 Ejecutar Suite de Pruebas'},
            {'v': 'clean', 'l': '🧹 Limpiar Sistema (Cache)'},
            {'v': 'shell', 'l': '💻 Shell Interactivo (Debug)'},
            {'v': 'exit', 'l': '🔌 Apagar'}
        ])

        if opt == 'run': os.system(f"{sys.executable} -m app.main"); input("...")
        elif opt == 'wizard': wizard(); input("...")
        elif opt == 'list': cmd_list_modules(); input("\nEnter...")
        elif opt == 'health': asyncio.run(cmd_health_check()); input("\nEnter...")
        elif opt == 'db' and INFRA_READY:
            if input(f"{C.RED}☢️ ¿RESET TOTAL? (y/N): {C.END}").lower() == 'y':
                async def r():
                    async with engine.begin() as c:
                        await c.run_sync(Base.metadata.drop_all)
                        await c.run_sync(Base.metadata.create_all)
                asyncio.run(r()); print("Hecho.")
            input("...")
        elif opt == 'test': 
            suite = unittest.TestLoader().discover('modules')
            unittest.TextTestRunner(verbosity=2).run(suite); input("...")
        elif opt == 'clean': cmd_cleanup(); input("...")
        elif opt == 'shell':
            try:
                from app.core.graph import Graph
                from app.core.orm import Model
                code.interact(banner=f"{C.GREEN}Kernel Shell. Graph & Model loaded.{C.END}", local=locals())
            except: print("Error cargando Core."); input("...")
        elif opt == 'exit': break

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: sys.exit(0)