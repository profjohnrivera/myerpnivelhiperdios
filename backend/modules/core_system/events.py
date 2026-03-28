# modules/core_system/events.py
from app.core.events import Event

class SequenceCreated(Event):
    """Evento disparado tras la creación exitosa de un registro."""
    def __init__(self, record_id): 
        self.record_id = record_id
