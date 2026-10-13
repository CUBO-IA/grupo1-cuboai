from decimal import ROUND_HALF_UP, Decimal

from django import forms

from .models import DogProfile

LB_TO_KG = Decimal("0.45359237")
IN_TO_CM = Decimal("2.54")

WEIGHT_UNITS = [("kg", "kg"), ("lb", "lb")]
LENGTH_UNITS = [("cm", "cm"), ("in", "in")]

# Rangos plausibles provisionales (docs/task-02-catalogo-datos.md): detectan
# errores de captura; no son reglas comerciales ni tallas. Valores en kg / cm.
WEIGHT_RANGE_KG = (Decimal("1"), Decimal("40"))
BACK_RANGE_CM = (Decimal("10"), Decimal("100"))
CHEST_RANGE_CM = (Decimal("15"), Decimal("120"))
NECK_RANGE_CM = (Decimal("10"), Decimal("70"))


def _quantize(value, places):
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


class SmartFitForm(forms.Form):
    name = forms.CharField(label="Dog's name", max_length=80)
    breed = forms.CharField(label="Breed", max_length=80)
    weight = forms.DecimalField(
        label="Weight", max_digits=6, decimal_places=2, min_value=Decimal("0.01")
    )
    weight_unit = forms.ChoiceField(label="Weight unit", choices=WEIGHT_UNITS)
    length_unit = forms.ChoiceField(label="Measurement unit", choices=LENGTH_UNITS)
    back_length = forms.DecimalField(
        label="Back length", max_digits=6, decimal_places=2, min_value=Decimal("0.01")
    )
    chest_girth = forms.DecimalField(
        label="Chest girth", max_digits=6, decimal_places=2, min_value=Decimal("0.01")
    )
    neck_girth = forms.DecimalField(
        label="Neck girth (optional)",
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )

    def clean(self):
        data = super().clean()
        weight_unit = data.get("weight_unit")
        length_unit = data.get("length_unit")

        if data.get("weight") is not None and weight_unit:
            kg = data["weight"]
            if weight_unit == "lb":
                kg = kg * LB_TO_KG
            data["weight_kg"] = self._check_range(
                "weight", _quantize(kg, 2), WEIGHT_RANGE_KG, "kg", LB_TO_KG, "lb"
            )

        if length_unit:
            for field, key, bounds in (
                ("back_length", "back_length_cm", BACK_RANGE_CM),
                ("chest_girth", "chest_girth_cm", CHEST_RANGE_CM),
                ("neck_girth", "neck_girth_cm", NECK_RANGE_CM),
            ):
                value = data.get(field)
                if value is None:
                    continue
                cm = value * IN_TO_CM if length_unit == "in" else value
                data[key] = self._check_range(
                    field, _quantize(cm, 1), bounds, "cm", IN_TO_CM, "in"
                )
        return data

    def _check_range(self, field, value, bounds, unit, factor, alt_unit):
        low, high = bounds
        if low <= value <= high:
            return value
        self.add_error(
            field,
            f"This value looks out of range. Expected about "
            f"{low:g}–{high:g} {unit} ({_quantize(low / factor, 1):g}–"
            f"{_quantize(high / factor, 1):g} {alt_unit}). "
            f"Please check the number and the unit.",
        )
        return None

    def save(self):
        d = self.cleaned_data
        return DogProfile.objects.create(
            name=d["name"],
            breed=d["breed"],
            weight_kg=d["weight_kg"],
            back_length_cm=d["back_length_cm"],
            chest_girth_cm=d["chest_girth_cm"],
            neck_girth_cm=d.get("neck_girth_cm"),
        )


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(label="Full name", max_length=120)
    customer_email = forms.EmailField(label="Email", max_length=254)
    customer_phone = forms.CharField(label="Phone", max_length=30)
    country = forms.CharField(label="Country", max_length=80)
    city = forms.CharField(label="City", max_length=80)
    address = forms.CharField(
        label="Delivery address", max_length=300, widget=forms.Textarea(attrs={"rows": 3})
    )

    def clean_customer_phone(self):
        phone = self.cleaned_data["customer_phone"]
        digits = [c for c in phone if c.isdigit()]
        allowed = set("+0123456789 ()-.")
        if len(digits) < 7 or len(digits) > 15 or not set(phone) <= allowed:
            raise forms.ValidationError(
                "Enter a valid phone number, e.g. +503 7000 0000."
            )
        return phone


class CostForm(forms.Form):
    estimated_cost = forms.DecimalField(
        label="Estimated cost (USD)", required=False, min_value=Decimal("0"),
        max_digits=10, decimal_places=2,
    )
    actual_cost = forms.DecimalField(
        label="Actual cost (USD)", required=False, min_value=Decimal("0"),
        max_digits=10, decimal_places=2,
    )
    cost_notes = forms.CharField(label="Notes", required=False, max_length=300)
