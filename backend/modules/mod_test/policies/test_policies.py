# backend/modules/mod_test/policies/test_policies.py
from app.core.policies import Policy

class TestAmountPolicy(Policy):
    """Política reactiva del Graph - Nivel Máximo"""
    name = "test.amount.warning"
    depends_on = {"data:test.model:*:amount"}

    def evaluate(self, inputs):
        amount = float(inputs.get("data:test.model:*:amount", 0))
        if amount > 100000:
            print(f"⚠️ HYPERDIOS ALERT: Monto excesivo → {amount}")
            return False
        return True