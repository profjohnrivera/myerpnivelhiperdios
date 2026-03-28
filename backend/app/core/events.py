# backend/app/core/events.py

class Event:
    pass

# 🔥 NUEVO: Evento genérico para acciones de UI
class UserAction(Event):
    def __init__(self, action_name: str, payload: dict) -> None:
        self.action_name = action_name # Ej: "update_profile"
        self.payload = payload         # Ej: {"user_id": "u1", "email": "nuevo@..."}