# backend/app/core/ui_registry.py

class UIRegistry:
    """
    🧠 CEREBRO VISUAL EN RAM
    Almacena los menús y vistas pre-compilados. Cero consultas a PostgreSQL.
    """
    _views = {}
    _menus = {}

    @classmethod
    def register_view(cls, view):
        compiled = view.compile()
        cls._views[compiled['id']] = compiled

    @classmethod
    def register_menu(cls, menu):
        compiled = menu.compile()
        cls._menus[compiled['id']] = compiled

    @classmethod
    def get_view(cls, view_id: str) -> dict:
        return cls._views.get(view_id)

    @classmethod
    def get_all_menus(cls) -> list:
        # Devuelve los menús ordenados por secuencia listos para el Frontend
        return sorted(cls._menus.values(), key=lambda x: x.get('sequence', 10))