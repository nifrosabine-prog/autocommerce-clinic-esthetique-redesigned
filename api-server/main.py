"""
AutoCommerce Clinic — Point d'entrée FastAPI

Ce fichier n'existait pas : l'API ne pouvait pas démarrer. Il monte
les routers de api/v1, expose /health (attendu par le healthcheck
Docker de docker-compose.clinic.yml), configure CORS, et ferme
proprement le pool de connexions DB à l'arrêt.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import logging
import os

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from middleware.request_context import RequestContextMiddleware, configure_logging
from middleware.request_timing import RequestTimingMiddleware
from api.v1 import (
    private_router,
    api_router as v1_router,
    public_gateway_router,
    legacy_public_gateway_router,
)
from api.deps import dispose_engine, limiter, get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Railway utilise actuellement une commande uvicorn personnalisée. Le seed
    # est donc exécuté ici en complément de start.sh afin de rester fiable
    # quelle que soit la commande de démarrage active.
    if os.getenv("BOOTSTRAP_ADMIN_EMAIL") or os.getenv("BOOTSTRAP_ADMIN_PASSWORD"):
        try:
            from bootstrap_admin import _bootstrap_from_environment
            await asyncio.to_thread(_bootstrap_from_environment)
        except Exception:
            # Le seed ne doit pas rendre l'application indisponible : l'admin
            # pourra être créé lors d'un redémarrage ultérieur après correction
            # de la dépendance concernée.
            logging.getLogger(__name__).warning(
                "Admin bootstrap failed during startup; continuing without seed",
                exc_info=True,
            )
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="AutoCommerce Clinic API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    allow_origins = ["*"] if settings.cors_origins.strip() == "*" else origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Mesure de la durée de chaque requête HTTP (P0-1) : journalisation en
    # WARNING des requêtes lentes (>= 5 s) ou en erreur, DEBUG sinon.
    app.add_middleware(RequestTimingMiddleware)

    # FastAPI 0.141 conserve les routeurs inclus comme `_IncludedRouter`.
    # Aplatir ici un niveau de composition rend les routes effectives tout en
    # conservant les frontières et préfixes historiques.
    def include_flat_router(aggregate_router) -> None:
        for child in aggregate_router.routes:
            original = getattr(child, "original_router", None)
            context = getattr(child, "include_context", None)
            if original is not None and context is not None:
                app.include_router(original, prefix=context.prefix)

    include_flat_router(public_gateway_router)
    include_flat_router(private_router)
    include_flat_router(v1_router)
    include_flat_router(legacy_public_gateway_router)

    settings.branding_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/branding", StaticFiles(directory=str(settings.branding_dir)), name="branding")

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def readiness(db: AsyncSession = Depends(get_db)):
        """Vérifie PostgreSQL et Redis sans divulguer les détails internes."""
        import logging
        from redis.asyncio import from_url as redis_from_url

        logger = logging.getLogger(__name__)
        postgres_ok = False
        redis_ok = False
        redis_client = None
        try:
            await db.execute(select(1))
            postgres_ok = True
            redis_client = redis_from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            redis_ok = True
        except Exception:
            logger.warning("Readiness dependency check failed", exc_info=True)
        finally:
            if redis_client is not None:
                try:
                    await redis_client.aclose()
                except Exception:
                    logger.debug("Redis readiness client close failed", exc_info=True)

        if postgres_ok and redis_ok:
            return {"status": "ready", "postgres": "ok", "redis": "ok"}
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    @app.get("/metrics", tags=["health"])
    async def metrics(current_user: dict = Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))):
        """Endpoint Prometheus — retourne les métriques instrumentation."""
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Instrumentation Prometheus (si Sentry/monitoring configuré)
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        # La route /metrics applicative reste protégée par RBAC ; ne pas
        # appeler expose(), qui ajouterait une route Prometheus publique.
        Instrumentator().instrument(app)
    except Exception:
        pass  # Prometheus non critique

    # En production, le build React est copié dans api-server/web-dist.
    # En recette locale, servir en priorité le build courant du monorepo afin
    # d’éviter qu’une copie web-dist obsolète masque les corrections validées.
    project_root = Path(__file__).resolve().parent.parent
    frontend_candidates = (
        project_root / "autocommerce-app" / "dist" / "public",
        Path(__file__).resolve().parent / "web-dist",
    )
    frontend_dir = next((candidate for candidate in frontend_candidates if (candidate / "index.html").is_file()), frontend_candidates[-1])
    frontend_root = frontend_dir.resolve()
    if frontend_root.is_dir() and (frontend_root / "index.html").is_file():
        assets_dir = frontend_root / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def frontend_spa(full_path: str):
            # Une route API inconnue doit rester une 404 JSON et ne doit pas
            # recevoir index.html du frontend.
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "API endpoint not found"}, status_code=404)
            requested = (frontend_root / full_path).resolve()
            if requested.is_file() and frontend_root in requested.parents:
                return FileResponse(requested)
            return FileResponse(frontend_root / "index.html")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
