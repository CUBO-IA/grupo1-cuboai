"""Método manual/transferencia: operativo REAL sin pasarela (§11.2).

Instrucciones configuradas por tienda + referencia + evidencia privada +
revisión humana autorizada. Un comprobante NO marca pagado automáticamente:
lo confirma un rol con capacidad (owner/finanzas) mediante apply_transition.
"""

from .base import AdapterResponse, PaymentAdapter


class ManualAdapter(PaymentAdapter):
    key = "manual"
    label = "Transferencia / efecto manual verificado por personas"

    def capabilities(self, account=None):
        # Operativo por definición: la "verificación" la hace una persona.
        return {"create": True, "capture": False, "refund": False,
                "webhook": False, "hosted": False, "configured": True,
                "manual_review": True}

    def validate_configuration(self, account):
        return AdapterResponse(ok=True, provider=self.key, state="ready",
                               safe={"mode": "revisión humana"})

    def create_payment(self, attempt):
        return AdapterResponse(
            ok=True, provider=self.key, state="pending",
            external_ref=f"manual-{attempt.public_id}",
            currency=attempt.currency, amount=str(attempt.amount),
            safe={"instructions": "El comprador recibe las instrucciones "
                                  "configuradas por la tienda en su página de pedido."})

    def get_payment(self, attempt):
        # El estado real lo fija la revisión humana (apply_transition).
        return AdapterResponse(ok=True, provider=self.key, state=attempt.state,
                               external_ref=attempt.external_ref)

    def refund(self, attempt, amount=None, note=""):
        # Reembolso manual: la UI guía el proceso y registra evidencia (§11.7).
        return AdapterResponse(
            ok=True, provider=self.key, state="refund_pending",
            external_ref=attempt.external_ref,
            safe={"manual": True,
                  "note": "Reembolso manual: registrar referencia bancaria real."})
