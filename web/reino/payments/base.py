"""Contrato del adaptador de cobro (§11.3).

Cada adaptador declara capacidades VERIFICADAS; las no soportadas devuelven
una respuesta de dominio explícita, jamás un éxito de prueba. Un adaptador
real tiene HTTP concreto, autenticación, límites y manejo de fallos; el
adaptador `fake` existe SÓLO para tests y va marcado como tal.
"""

from dataclasses import dataclass, field


@dataclass
class AdapterResponse:
    """Respuesta normalizada (§11.3): proveedor, cuenta, entorno, referencia
    externa, moneda, importe, estado, fecha y datos seguros para continuar."""
    ok: bool
    provider: str
    state: str = ""                 # estado NORMALIZADO del contrato
    provider_state: str = ""        # estado original del proveedor (conservado)
    external_ref: str = ""
    currency: str = ""
    amount: str = ""
    redirect_url: str = ""          # método hospedado
    qr_payload: str = ""            # factura Bitcoin
    error: str = ""                 # mensaje de dominio comprensible
    safe: dict = field(default_factory=dict)


class PaymentAdapter:
    key = "base"
    label = "Adaptador base"

    def capabilities(self, account=None) -> dict:
        """Capacidades VERIFICADAS de ESTA cuenta/entorno (nunca por clase)."""
        return {"create": False, "capture": False, "refund": False,
                "webhook": False, "hosted": False, "configured": False}

    def validate_configuration(self, account) -> AdapterResponse:
        raise NotImplementedError

    def create_payment(self, attempt) -> AdapterResponse:
        raise NotImplementedError

    def get_payment(self, attempt) -> AdapterResponse:
        raise NotImplementedError

    def verify_notification(self, headers, raw_body) -> bool:
        """Autenticidad por el mecanismo oficial; si no hay prueba suficiente,
        la notificación es sólo una señal para consultar la API (§11.7)."""
        return False

    def capture(self, attempt) -> AdapterResponse:
        return AdapterResponse(ok=False, provider=self.key, error="captura no soportada")

    def cancel_or_void(self, attempt) -> AdapterResponse:
        return AdapterResponse(ok=False, provider=self.key, error="anulación no soportada")

    def refund(self, attempt, amount=None, note="") -> AdapterResponse:
        return AdapterResponse(ok=False, provider=self.key, error="reembolso no soportado")
