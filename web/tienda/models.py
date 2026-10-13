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
    def number(self):
        return f"WK-{self.pk:06d}"

    def __str__(self):
        return self.number
