from django.db import models


class DogProfile(models.Model):
    """Medidas de un perro, guardadas en unidades métricas (kg / cm)."""

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
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quote #{self.pk} - {self.product_slug}"


class Order(models.Model):
    """Pedido generado a partir de una cotización aceptada."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    quote = models.OneToOneField(
        Quote, on_delete=models.PROTECT, related_name="order"
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk}"
