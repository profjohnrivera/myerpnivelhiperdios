# modules/core_system/tests/test_logic.py
import unittest
from ..models import Sequence

class TestSequence(unittest.TestCase):
    def test_lifecycle(self):
        """Prueba el ciclo de vida básico del documento."""
        obj = Sequence(_id='test_1')
        self.assertTrue(obj.active, "El registro debe nacer activo")
        self.assertEqual(obj.state, "draft", "El estado inicial debe ser borrador")
