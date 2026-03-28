# backend/modules/mod_sales/data/rules.py

# 💎 FIX: Cambiamos "init_rules" a "skip_rules" para que el Ingestor lo ignore por ahora
async def skip_rules(env):
    """Reglas de seguridad temporalmente en pausa."""
    pass