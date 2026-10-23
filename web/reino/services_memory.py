"""Royal Passport: perfiles, medidas, consentimiento y borrado de memoria.

Reglas (S10/§12):
- El consentimiento no viene premarcado; navegar o pagar no equivale a autorizar.
- Retirar consentimiento impide reutilizar los datos y elimina derivados.
- Dos perros no comparten datos por coincidencia de nombre: selección por ID.
"""

from django.utils import timezone

from .models import Consent, Measurement, MemorySummary, Preference, RecipientProfile


def get_profile(store, session_key, public_id):
    """Perfil por ID validado contra tienda y propietario (fail-closed)."""
    return RecipientProfile.objects.filter(
        store=store, session_key=session_key, public_id=public_id
    ).first()


def list_profiles(store, session_key):
    return list(RecipientProfile.objects.filter(store=store, session_key=session_key))


def create_profile(store, session_key, alias, kind="dog", breed="", photo_path=""):
    return RecipientProfile.objects.create(
        store=store, session_key=session_key, alias=alias.strip()[:80] or "Sin nombre",
        kind=kind, breed=breed.strip()[:80], photo_path=photo_path,
    )


def latest_measurement(profile):
    return profile.measurements.first()


def save_measurement(profile, chest_cm=None, neck_cm=None, back_cm=None, original=None,
                     source="owner"):
    """Medidas nuevas versionan las anteriores (historial conservado)."""
    return Measurement.objects.create(
        profile=profile, chest_cm=chest_cm, neck_cm=neck_cm, back_cm=back_cm,
        original=original or {}, source=source,
    )


def has_consent(store, session_key, purpose, profile=None):
    qs = Consent.objects.filter(
        store=store, session_key=session_key, purpose=purpose, status=Consent.Status.GRANTED
    )
    if profile is not None:
        qs = qs.filter(profile__in=(profile, None))
    return qs.exists()


def grant_consent(store, session_key, purpose, profile=None, version="v1"):
    """Registra permiso explícito (clic del usuario, nunca del modelo)."""
    consent, _ = Consent.objects.update_or_create(
        store=store, session_key=session_key, purpose=purpose, profile=profile,
        defaults={"status": Consent.Status.GRANTED, "version": version, "revoked_at": None},
    )
    return consent


def revoke_consent(store, session_key, purpose, profile=None):
    qs = Consent.objects.filter(
        store=store, session_key=session_key, purpose=purpose, status=Consent.Status.GRANTED
    )
    if profile is not None:
        qs = qs.filter(profile=profile)
    n = 0
    for consent in qs:
        consent.status = Consent.Status.REVOKED
        consent.revoked_at = timezone.now()
        consent.save(update_fields=["status", "revoked_at"])
        # Los derivados de ese permiso dejan de existir.
        Preference.objects.filter(consent=consent).delete()
        n += 1
    return n


def save_preference(profile, consent, key, value, source="explicit"):
    pref, _ = Preference.objects.update_or_create(
        profile=profile, key=key[:40],
        defaults={"value": str(value)[:120], "source": source, "consent": consent},
    )
    return pref


def authorized_preferences(profile, store, session_key):
    """Solo preferencias con consentimiento vigente (A14)."""
    if not has_consent(store, session_key, Consent.Purpose.PREFERENCES, profile):
        return {}
    return {p.key: p.value for p in profile.preferences.all()}


def delete_profile_memory(store, session_key, profile):
    """Borra memoria del perfil: foto, preferencias, resúmenes y medidas opcionales.

    No toca pedidos (otra base de conservación) ni documentos públicos.
    """
    profile.preferences.all().delete()
    profile.memory_summaries.all().delete()
    profile.consents.update(status=Consent.Status.REVOKED, revoked_at=timezone.now())
    profile.photo_path = ""
    profile.save(update_fields=["photo_path"])
    return True


def consent_state(store, session_key, profile=None):
    """Estado visible de permisos para la pantalla de privacidad."""
    qs = Consent.objects.filter(store=store, session_key=session_key)
    if profile is not None:
        qs = qs.filter(profile__in=(profile, None))
    state = {}
    for purpose, label in Consent.Purpose.choices:
        c = qs.filter(purpose=purpose).order_by("-granted_at").first()
        state[purpose] = {
            "label": label,
            "status": c.status if c else "none",
            "granted_at": c.granted_at if c else None,
            "version": c.version if c else None,
        }
    return state
