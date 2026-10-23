"""Reino Commerce — modelo de datos multi-tienda (P0).

Decisiones clave (ver docs/02_ARQUITECTURA_Y_DATOS.md):
- Merchant es el tenant; en P0 cada Merchant tiene una Store.
- Todo registro de negocio cuelga de store (tenant) y las consultas se hacen
  siempre con el store resuelto en servidor (fail-closed sin tenant).
- Dinero en Decimal con una única política de redondeo (ver reino.money).
- Los snapshots de pedido no cambian al editar el catálogo.
"""

import uuid

from django.db import models
from django.utils import timezone


class Merchant(models.Model):
    """Comercio (tenant). Propietario contractual de una o más tiendas."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PILOT = "pilot", "Piloto"
        ACTIVE = "active", "Activo"
        SUSPENDED = "suspended", "Suspendido"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=120)
    country = models.CharField(max_length=80, default="El Salvador")
    contact_email = models.EmailField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    """Tienda pública de un Merchant. slug único; estado demo nunca cobra."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        DEMO = "demo", "Demostración"
        ACTIVE = "active", "Activa"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="stores")
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    tagline = models.CharField(max_length=160, blank=True)
    promise = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="USD")
    locale = models.CharField(max_length=10, default="es-SV")
    category = models.CharField(max_length=60, default="general")
    is_demo = models.BooleanField(default=False)  # contenido de prueba, sin cobros reales
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    pickup_address = models.CharField(max_length=200, blank=True)
    theme = models.JSONField(default=dict)  # tokens de marca por tienda
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (/s/{self.slug}/)"


class MerchantMember(models.Model):
    """Membresía usuario↔tenant con rol. Unicidad usuario+tenant."""

    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        STAFF = "staff", "Equipo"
        LOGISTICS = "logistics", "Logística"

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="memberships")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STAFF)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "merchant")

    def __str__(self):
        return f"{self.user} @ {self.merchant} ({self.role})"


# ---------------------------------------------------------------- catálogo --

class Product(models.Model):
    """Producto publicado en una tienda (catálogo en base de datos)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"
        ARCHIVED = "archived", "Archivado"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="products")
    slug = models.SlugField(max_length=80)
    legacy_slug = models.CharField(max_length=50, blank=True)  # enlace con catálogo histórico
    title = models.CharField(max_length=160)
    short_title = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=200, blank=True)  # beneficio verificable
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, default="general")
    occasions = models.JSONField(default=list)  # p. ej. ["celebracion", "paseo"]
    styles = models.JSONField(default=list)     # p. ej. ["royal-classic"]
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_featured = models.BooleanField(default=False)
    reason = models.CharField(max_length=160, blank=True)  # una razón verificable
    materials = models.JSONField(default=list)
    care = models.JSONField(default=list)
    shipping_note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("store", "slug")
        ordering = ["-is_featured", "short_title"]

    def __str__(self):
        return f"{self.short_title} ({self.store.slug})"


class FitRule(models.Model):
    """Regla de talla versionada por producto (rangos en cm).

    Medidas desconocidas nunca se interpretan como compatibles.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="fit_rules")
    version = models.PositiveSmallIntegerField(default=1)
    requires_neck = models.BooleanField(default=False)
    ease_note = models.CharField(max_length=200, blank=True)  # holgura propia del producto
    # Filas: [{"label":"S","chest_min":30,"chest_max":36,"neck_min":..,"back_min":..}, ...]
    ranges = models.JSONField(default=list)
    approved_by = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "version")
        ordering = ["-version"]

    def __str__(self):
        return f"FitRule v{self.version} · {self.product.short_title}"


class Variant(models.Model):
    """Variante comprable (SKU). SKU único por tienda; stock nunca negativo."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=60)
    option_label = models.CharField(max_length=60)  # p. ej. "Talla M", "Único"
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("product", "sku")
        ordering = ["pk"]

    @property
    def price(self):
        return self.price_override if self.price_override is not None else self.product.base_price

    def __str__(self):
        return f"{self.sku} · {self.product.short_title}"


class ProductMedia(models.Model):
    """Imagen pública de producto (ruta estática) con alt y origen/licencia."""

    class Kind(models.TextChoices):
        PRODUCT = "product", "Producto"
        USE = "use", "En uso"
        DETAIL = "detail", "Detalle"
        FIT = "fit", "Ajuste"
        EDITORIAL = "editorial", "Ilustración editorial"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    path = models.CharField(max_length=200)  # ruta dentro de static/
    alt = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PRODUCT)
    position = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=200, blank=True)  # origen/licencia de la imagen

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return f"{self.path} · {self.product.short_title}"


# ------------------------------------------------------------- compra (P0) --

class Cart(models.Model):
    """Carrito por tienda y sesión. Abrirlo no reserva inventario."""

    class Status(models.TextChoices):
        OPEN = "open", "Abierto"
        ORDERED = "ordered", "Convertido en pedido"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="carts")
    session_key = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    version = models.PositiveIntegerField(default=1)  # control optimista
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart {self.public_id} ({self.store.slug})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField(default=1)
    recipient = models.ForeignKey(
        "RecipientProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot al añadir
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "variant", "recipient")
        ordering = ["added_at", "pk"]


class CheckoutSession(models.Model):
    """Resumen aprobado de un intento de compra (idempotente)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.PROTECT, related_name="checkouts")
    cart_version = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=80, unique=True)
    summary = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() >= self.expires_at


class StockReservation(models.Model):
    """Reserva corta de stock durante el checkout (P0: 10 minutos)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        CONSUMED = "consumed", "Consumida"
        EXPIRED = "expired", "Vencida"
        RELEASED = "released", "Liberada"

    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, related_name="reservations")
    checkout = models.ForeignKey(CheckoutSession, on_delete=models.CASCADE, related_name="reservations")
    quantity = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    """Pedido de la tienda nueva. Estados separados: pedido/pago/preparación/entrega."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PLACED = "placed", "Colocado"
        CONFIRMED = "confirmed", "Confirmado"
        CANCELLED = "cancelled", "Cancelado"
        CLOSED = "closed", "Cerrado"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pendiente"
        REQUIRES_ACTION = "requires_action", "Requiere acción"
        PAID = "paid", "Pagado"
        FAILED = "failed", "Fallido"
        EXPIRED = "expired", "Vencido"
        REFUNDED = "refunded", "Reembolsado"
        PARTIALLY_REFUNDED = "partially_refunded", "Parcialmente reembolsado"
        DISPUTED = "disputed", "En disputa"

    class PrepStatus(models.TextChoices):
        NOT_STARTED = "not_started", "No iniciada"
        PREPARING = "preparing", "Preparando"
        READY = "ready", "Lista"
        CANCELLED = "cancelled", "Cancelada"

    class DeliveryStatus(models.TextChoices):
        UNASSIGNED = "unassigned", "Sin asignar"
        SCHEDULED = "scheduled", "Programada"
        SHIPPED = "shipped", "Despachada"
        DELIVERED = "delivered", "Entregada"
        INCIDENT = "incident", "Incidencia"
        RETURNED = "returned", "Devuelta"

    class PaymentMethod(models.TextChoices):
        MANUAL = "manual", "Pago manual (verificación)"
        BITCOIN = "bitcoin", "Bitcoin (manual)"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=16, db_index=True)  # p. ej. WK-000123
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # invitados
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="orders")
    cart = models.OneToOneField(Cart, null=True, blank=True, on_delete=models.PROTECT, related_name="order")
    idempotency_key = models.CharField(max_length=80, unique=True)
    currency = models.CharField(max_length=3, default="USD")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_note = models.CharField(max_length=120, blank=True)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    customer_name = models.CharField(max_length=120)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=40, blank=True)
    delivery_mode = models.CharField(max_length=12, default="pickup")  # pickup | local
    address = models.TextField(max_length=300, blank=True)
    city = models.CharField(max_length=80, blank=True)
    zone = models.CharField(max_length=80, blank=True)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.MANUAL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLACED)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    prep_status = models.CharField(max_length=12, choices=PrepStatus.choices, default=PrepStatus.NOT_STARTED)
    delivery_status = models.CharField(max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.UNASSIGNED)
    payment_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    """Línea de pedido con snapshot histórico (no cambia al editar catálogo)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField(default=0)
    variant = models.ForeignKey(Variant, null=True, on_delete=models.SET_NULL, related_name="+")
    sku = models.CharField(max_length=60)
    title = models.CharField(max_length=160)
    option_label = models.CharField(max_length=60, blank=True)
    recipient_alias = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["position", "pk"]


class OrderEvent(models.Model):
    """Línea temporal auditable del pedido (quién cambió qué)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    field = models.CharField(max_length=30)
    from_value = models.CharField(max_length=24, blank=True)
    to_value = models.CharField(max_length=24)
    note = models.CharField(max_length=200, blank=True)
    by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class OutboxEvent(models.Model):
    """Trabajo diferido recuperable tras fallo (emails, métricas, webhooks)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        DONE = "done", "Procesado"
        FAILED = "failed", "Fallido"

    type = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    retries = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)


# ------------------------------------------------- perfiles, memoria y RAG --

class RecipientProfile(models.Model):
    """Perfil de destinatario (Royal Passport). Identidad por ID, nunca por nombre."""

    class Kind(models.TextChoices):
        DOG = "dog", "Perro"
        OTHER = "other", "Otro destinatario"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="profiles")
    session_key = models.CharField(max_length=64, db_index=True)  # propietario (P0: sesión)
    alias = models.CharField(max_length=80)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.DOG)
    breed = models.CharField(max_length=80, blank=True)
    photo_path = models.CharField(max_length=200, blank=True)  # opcional, nunca obligatoria
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alias} ({self.store.slug})"


class Measurement(models.Model):
    """Medidas de un perfil: valor original + normalizadas a cm, con fecha y origen."""

    profile = models.ForeignKey(RecipientProfile, on_delete=models.CASCADE, related_name="measurements")
    chest_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    neck_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    back_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    original = models.JSONField(default=dict)  # {"chest": 15, "unit": "in", ...}
    source = models.CharField(max_length=20, default="owner")  # owner | looklab | smartfit
    measured_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-measured_at", "-pk"]


class Consent(models.Model):
    """Permiso de memoria por titular, tienda y finalidad. Revocable."""

    class Purpose(models.TextChoices):
        MEASUREMENTS = "measurements", "Guardar medidas"
        PREFERENCES = "preferences", "Guardar preferencias"
        PERSONALIZATION = "personalization", "Personalización"

    class Status(models.TextChoices):
        GRANTED = "granted", "Otorgado"
        REVOKED = "revoked", "Revocado"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="consents")
    session_key = models.CharField(max_length=64, db_index=True)
    profile = models.ForeignKey(RecipientProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="consents")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    version = models.CharField(max_length=20, default="v1")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.GRANTED)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-granted_at"]


class Preference(models.Model):
    """Preferencia persistente con consentimiento y origen."""

    profile = models.ForeignKey(RecipientProfile, on_delete=models.CASCADE, related_name="preferences")
    consent = models.ForeignKey(Consent, on_delete=models.CASCADE, related_name="preferences")
    key = models.CharField(max_length=40)   # p. ej. "color", "occasion", "budget_hint"
    value = models.CharField(max_length=120)
    source = models.CharField(max_length=20, default="explicit")  # explicit | assistant
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("profile", "key")


class MemorySummary(models.Model):
    """Resumen contextual derivado, corto, con referencias. Se invalida al revocar."""

    profile = models.ForeignKey(RecipientProfile, on_delete=models.CASCADE, related_name="memory_summaries")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="memory_summaries")
    summary = models.CharField(max_length=280)
    refs = models.JSONField(default=list)
    consent_version = models.CharField(max_length=20, default="v1")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Look(models.Model):
    """Look guardado de LookLab. Guardar un look no reserva precio ni stock."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="looks")
    session_key = models.CharField(max_length=64, db_index=True)
    profile = models.ForeignKey(RecipientProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="looks")
    occasion = models.CharField(max_length=40, blank=True)
    style = models.CharField(max_length=40, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    items = models.JSONField(default=list)  # [{"variant_id":..,"title":..,"price":..}]
    recommender_version = models.CharField(max_length=20, default="v1")
    created_at = models.DateTimeField(auto_now_add=True)


class KnowledgeDocument(models.Model):
    """Documento publicado de una tienda para el RAG (guías, políticas)."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="knowledge")
    audience = models.CharField(max_length=20, default="customer")  # customer | staff
    topic = models.CharField(max_length=40)   # tallas | envios | cambios | compra | cuidado
    title = models.CharField(max_length=160)
    body = models.TextField()
    version = models.CharField(max_length=20, default="v1")
    is_published = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=120, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["topic", "title"]


# ------------------------------------------------------------------- IA -----

class AIConversation(models.Model):
    """Conversación del asesor. Propietario = sesión (P0)."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="conversations")
    session_key = models.CharField(max_length=64, db_index=True)
    mode = models.CharField(max_length=12, default="rules")  # ai | rules (etiqueta honesta)
    created_at = models.DateTimeField(auto_now_add=True)


class AIMessage(models.Model):
    conversation = models.ForeignKey(AIConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10)  # user | assistant | system
    content = models.TextField()
    cards = models.JSONField(default=list)   # tarjetas renderizadas desde IDs validados
    request_id = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class RecommendationEvent(models.Model):
    """Trazabilidad de recomendaciones: candidatos, exclusiones, razones, versión."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="recommendation_events")
    request_id = models.CharField(max_length=40, db_index=True)
    kind = models.CharField(max_length=20, default="looklab")  # looklab | stylist | search
    intent = models.JSONField(default=dict)
    candidates = models.JSONField(default=list)
    excluded = models.JSONField(default=list)
    reasons = models.JSONField(default=list)
    engine_version = models.CharField(max_length=20, default="v1")
    created_at = models.DateTimeField(auto_now_add=True)


class ShippingZone(models.Model):
    """Zona de entrega configurada por el comerciante (matriz P0)."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="shipping_zones")
    name = models.CharField(max_length=80)          # p. ej. "San Salvador"
    mode = models.CharField(max_length=12, default="local")  # pickup | local
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    eta_note = models.CharField(max_length=120, blank=True)  # rango estimado o "Por confirmar"
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
