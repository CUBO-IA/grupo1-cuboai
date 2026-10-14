import uuid

from django.db import models


class DogProfile(models.Model):
    """Medidas de un perro, guardadas en unidades métricas (kg / cm)."""

    # Identificador público no secuencial para las URLs.
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=80)
    breed = models.CharField(max_length=80)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2)
    back_length_cm = models.DecimalField(max_digits=5, decimal_places=1)
    chest_girth_cm = models.DecimalField(max_digits=5, decimal_places=1)
    neck_girth_cm = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.breed})"


class Quote(models.Model):
    """Cotización de un producto del catálogo para un perro."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dog = models.ForeignKey(
        DogProfile, on_delete=models.PROTECT, related_name="quotes"
    )
    # El catálogo vive en tienda.views.PRODUCTOS; se referencia por su clave.
    product_slug = models.CharField(max_length=50)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Nulo hasta que exista una regla comercial de precio por talla.
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    class Pricing(models.TextChoices):
        PROVISIONAL = "provisional", "Provisional"
        FINAL = "final", "Final"

    # Provisional: solo precio base, sin ajuste por talla (regla comercial
    # pendiente). Final: total validado con una regla comercial aprobada.
    pricing = models.CharField(
        max_length=20, choices=Pricing.choices, default=Pricing.PROVISIONAL
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quote #{self.pk} - {self.product_slug}"


class Order(models.Model):
    """Pedido generado a partir de una cotización.

    Pago, producción y envío son estados independientes. Crear el pedido
    NO implica que esté pagado.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"

    class ProductionStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PRODUCTION = "in_production", "In production"
        COMPLETED = "completed", "Completed"

    class PaymentMethod(models.TextChoices):
        UNSPECIFIED = "unspecified", "To be arranged"
        BITCOIN = "bitcoin", "Bitcoin"

    class DiscountStatus(models.TextChoices):
        NONE = "none", "None"
        PENDING = "pending_verification", "Pending payment verification"
        APPLIED = "applied", "Applied"

    class ShippingStatus(models.TextChoices):
        NOT_SHIPPED = "not_shipped", "Not shipped"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    quote = models.OneToOneField(
        Quote, on_delete=models.PROTECT, related_name="order"
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    # True mientras no exista regla de precio por talla aprobada.
    price_is_provisional = models.BooleanField(default=True)

    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)
    country = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    address = models.TextField(max_length=300)

    # Copia de producto, precio y medidas al momento de crear el pedido.
    snapshot = models.JSONField(default=dict)

    # Evidencia aportada por el personal al marcar el pago (p. ej. referencia).
    payment_reference = models.CharField(max_length=120, blank=True)

    # Método de pago elegido y descuento Bitcoin (15 % sobre el subtotal de
    # productos, sin envío). El descuento queda PENDIENTE hasta que el pago
    # sea verificado; `total` es siempre el subtotal de productos.
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.UNSPECIFIED
    )
    discount_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_status = models.CharField(
        max_length=24, choices=DiscountStatus.choices, default=DiscountStatus.NONE
    )

    # Costos internos. Estimado y real son valores distintos; ambos opcionales.
    # Los totales se derivan de materiales + mano de obra cuando se cargan.
    estimated_materials = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    estimated_labor = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    actual_materials = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    actual_labor = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    estimated_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    actual_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    cost_notes = models.CharField(max_length=300, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    production_status = models.CharField(
        max_length=20,
        choices=ProductionStatus.choices,
        default=ProductionStatus.NOT_STARTED,
    )
    shipping_status = models.CharField(
        max_length=20,
        choices=ShippingStatus.choices,
        default=ShippingStatus.NOT_SHIPPED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def amount_due(self):
        """Importe a pagar: el descuento solo cuenta cuando está aplicado."""
        if self.discount_status == self.DiscountStatus.APPLIED:
            return self.total - self.discount_amount
        return self.total

    @property
    def amount_if_discount(self):
        return self.total - self.discount_amount

    @property
    def number(self):
        return f"WK-{self.pk:06d}"

    def __str__(self):
        return self.number


class OrderEvent(models.Model):
    """Registro de cada cambio de estado hecho desde el panel."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    field = models.CharField(max_length=30)
    from_value = models.CharField(max_length=20)
    to_value = models.CharField(max_length=20)
    note = models.CharField(max_length=200, blank=True)
    by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class ProductCost(models.Model):
    """Presupuesto interno de fabricación de un producto del catálogo.

    PRIVADO: nunca se muestra en páginas públicas. Todos los valores son
    supuestos editables hasta que `is_validated` sea verdadero.
    """

    product_slug = models.CharField(max_length=50, unique=True)
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_costs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_validated = models.BooleanField(default=False)
    notes = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return f"Cost profile {self.product_slug}"


class MaterialLine(models.Model):
    """Partida de materiales: consumo × precio unitario = subtotal."""

    product_cost = models.ForeignKey(
        ProductCost, on_delete=models.CASCADE, related_name="lines"
    )
    position = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=8, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Reservas sin desglose confirmado de insumos.
    is_provisional_reserve = models.BooleanField(default=False)
    is_validated = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "pk"]

    @property
    def subtotal(self):
        from decimal import ROUND_HALF_UP, Decimal

        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def __str__(self):
        return f"{self.name} ({self.product_cost.product_slug})"
