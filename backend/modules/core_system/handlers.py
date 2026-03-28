# modules/core_system/handlers.py
import logging
from .events import SequenceCreated

logger = logging.getLogger(__name__)

async def on_sequence_created(event: SequenceCreated):
    """
    Handler Asíncrono: Reacciona a la creación del registro.
    Ideal para: Enviar correos, actualizar contadores, notificaciones push.
    """
    try:
        logger.info(f"✨ Nuevo Sequence detectado: {event.record_id}")
        # TODO: Implementar lógica de negocio (ej: Email de bienvenida)
        # service.send_email(event.record_id)
    except Exception as e:
        logger.error(f"❌ Error en handler on_sequence_created: {e}")
