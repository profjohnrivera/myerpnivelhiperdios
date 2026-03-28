# backend/app/core/ui.py

class Node:
    """
    🧬 ADN VISUAL BASE
    Clase base para todos los elementos de la interfaz.
    Implementa el motor de compilación que transforma Python en JSON/MsgPack.
    """
    def compile(self) -> dict:
        """Convierte el objeto Python y sus hijos en un diccionario puro hiper-rápido."""
        # El tipo se define por el nombre de la clase (Field, Form, etc.)
        res = {"type": self.__class__.__name__}
        
        for k, v in self.__dict__.items():
            # Ignoramos nulos y atributos privados del sistema
            if v is None or k.startswith('_'): 
                continue
            
            # Compilación recursiva de listas (hijos)
            if isinstance(v, list):
                res[k] = [i.compile() if isinstance(i, Node) else i for i in v]
            # Compilación de nodos anidados
            elif isinstance(v, Node):
                res[k] = v.compile()
            # Valores primitivos (str, int, bool)
            else:
                res[k] = v
        return res

# ==========================================
# --- COMPONENTES VISUALES (El Alfabeto) ---
# ==========================================

class Field(Node):
    """Representa un campo de datos vinculado al modelo."""
    def __init__(self, name: str, widget: str = None, readonly: bool = False, **kwargs):
        self.name = name
        self.widget = widget
        self.readonly = readonly
        # Permitimos atributos extra para widgets específicos (ej: placeholder, mask)
        for k, v in kwargs.items():
            setattr(self, k, v)

class Row(Node):
    """Contenedor horizontal para organizar campos en la misma línea."""
    def __init__(self, *children):
        self.children = list(children)

class Group(Node):
    """Agrupador lógico con título (Caja visual)."""
    def __init__(self, string: str = None, *children):
        self.string = string
        self.children = list(children)

class Page(Node):
    """Una pestaña individual dentro de un Notebook."""
    def __init__(self, title: str, *children):
        self.title = title
        self.children = list(children)

class Notebook(Node):
    """Contenedor de pestañas (Tabs)."""
    def __init__(self, *pages):
        self.pages = list(pages)

class Form(Node):
    """Vista de edición/creación de un registro único."""
    def __init__(self, *children):
        self.children = list(children)

class List(Node):
    """Vista de tabla (Grilla) para múltiples registros."""
    def __init__(self, *fields):
        self.children = list(fields)

# ==========================================
# --- CONTENEDORES MAESTROS ---
# ==========================================

class View(Node):
    """
    📦 CONTENEDOR DE ARQUITECTURA
    Une un modelo con una estructura visual específica.
    """
    def __init__(self, id: str, model: str, name: str, arch: Node):
        self.id = id
        self.model = model
        self.name = name
        self.arch = arch

class Menu(Node):
    """
    🗺️ SISTEMA DE NAVEGACIÓN
    Define la jerarquía del menú principal del ERP.
    """
    def __init__(self, id: str, name: str, parent_id: str = None, action: str = None, icon: str = None, sequence: int = 10):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.action = action  # El ID de la View o Action a disparar
        self.icon = icon
        self.sequence = sequence