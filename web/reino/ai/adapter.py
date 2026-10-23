"""Adaptador de proveedor de IA (OpenAI-compatible, §10).

- Clave fuera del repositorio (settings.REINO_AI desde entorno).
- Entradas y salidas tipadas; timeout configurable; sin reenviar todo el
  historial en cada turno (se acota).
- `available()` distingue honestamente el modo del asesor: con clave real el
  modo es "ai"; sin ella, "rules" (nunca se simula una respuesta del modelo).
"""

import json
import urllib.error
import urllib.request

from django.conf import settings


class ProviderError(Exception):
    pass


class ProviderUnavailable(ProviderError):
    """Sin clave o proveedor inalcanzable: el orquestador degrada con honestidad."""


def available():
    return bool(settings.REINO_AI.get("API_KEY"))


def chat(messages, tools=None):
    """Una llamada chat.completions. Devuelve el dict del primer mensaje."""
    cfg = settings.REINO_AI
    if not cfg.get("API_KEY"):
        raise ProviderUnavailable("Sin REINO_AI_API_KEY configurada.")
    payload = {
        "model": cfg["MODEL"],
        "messages": messages,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    req = urllib.request.Request(
        f"{cfg['BASE_URL'].rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['API_KEY']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg["TIMEOUT_SECONDS"]) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()[:300]
        raise ProviderError(f"HTTP {exc.code}: {body}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderUnavailable(str(exc)) from None
    try:
        return data["choices"][0]["message"]
    except (KeyError, IndexError):
        raise ProviderError("Respuesta del proveedor sin choices.") from None
