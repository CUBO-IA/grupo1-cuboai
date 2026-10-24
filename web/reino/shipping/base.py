"""Contrato del adaptador de transporte (§12.3): capacidades declaradas por
cuenta; las operaciones inexistentes devuelven dominio explícito. El flujo
MANUAL es completo y no depende de ningún proveedor.
"""

from dataclasses import dataclass, field


@dataclass
class ShipResponse:
    ok: bool
    provider: str
    state: str = ""
    provider_state: str = ""
    external_ref: str = ""
    tracking: str = ""
    label_url: str = ""
    amount: str = ""
    currency: str = ""
    eta: str = ""
    error: str = ""
    safe: dict = field(default_factory=dict)


class ShippingAdapter:
    key = "base"
    label = "Base"

    def capabilities(self, account=None) -> dict:
        return {"quote": False, "create": False, "label": False,
                "track": False, "cancel": False, "configured": False}

    def validate_address(self, address: dict) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="no soportado")

    def list_services(self, origin, destination, packages) -> list:
        return []

    def quote(self, origin, destination, packages, service=None) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="cotización no soportada")

    def create_shipment(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="creación no soportada")

    def get_label(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="etiqueta no soportada")

    def track(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="tracking no soportado")

    def cancel_shipment(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="cancelación no soportada")

    def request_pickup(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="recolección no soportada")

    def create_return(self, shipment) -> ShipResponse:
        return ShipResponse(ok=False, provider=self.key, error="devolución no soportada")
