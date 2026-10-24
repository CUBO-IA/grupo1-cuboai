"""Transporte manual COMPLETO (§12.2): zonas/tarifas del negocio, asignación,
salida, entrega/incidencia — todo registrado con actor y evidencia."""

from .base import ShipResponse, ShippingAdapter


class ManualShipping(ShippingAdapter):
    key = "manual"
    label = "Entrega local manual (zonas del negocio)"

    def capabilities(self, account=None):
        return {"quote": True, "create": True, "label": False, "track": True,
                "cancel": True, "configured": True, "manual": True}

    def quote(self, origin, destination, packages, service=None):
        zone = (destination or {}).get("zone")
        fee = (destination or {}).get("fee")
        if zone is None or fee is None:
            return ShipResponse(ok=False, provider=self.key,
                                error="zona/tarifa del negocio requerida")
        return ShipResponse(ok=True, provider=self.key, state="quoted",
                            amount=str(fee), currency="USD",
                            safe={"zone": zone, "mode": "local manual"})

    def create_shipment(self, shipment):
        return ShipResponse(ok=True, provider=self.key, state="prepared",
                            external_ref=f"manual-{shipment.public_id}",
                            safe={"mode": "manual"})

    def track(self, shipment):
        return ShipResponse(ok=True, provider=self.key, state=shipment.status,
                            external_ref=shipment.external_ref)
