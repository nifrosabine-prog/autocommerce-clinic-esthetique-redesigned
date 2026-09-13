"""
AutoCommerce Clinic — Middleware de mesure des temps de requête (P0-1)

Objectif : objectiver la cause racine des délais de réactivation observés
(~45 s lors de l'audit) et rendre visible tout endpoint lent. Chaque requête
HTTP est chronométrée ; les requêtes lentes (>= SLOW_MS) ou en erreur
(statut >= 400) sont journalisées en WARNING, les autres en DEBUG.
"""

import logging
import time

logger = logging.getLogger("api.timing")

# Seuil au-delà duquel une requête est considérée anormale.
SLOW_MS = 5_000.0


def is_slow(duration_ms: float) -> bool:
    return duration_ms >= SLOW_MS


class RequestTimingMiddleware:
    """Mesure la durée totale d'une requête HTTP et la journalise."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_holder = {"code": 0}

        async def _send(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000.0
            method = scope.get("method", "")
            path = scope.get("path", "")
            status = status_holder["code"]
            if is_slow(duration_ms) or status >= 400:
                logger.warning(
                    "request_slow_or_error method=%s path=%s status=%s duration_ms=%.1f",
                    method, path, status, duration_ms,
                )
            else:
                logger.debug(
                    "request method=%s path=%s status=%s duration_ms=%.1f",
                    method, path, status, duration_ms,
                )
