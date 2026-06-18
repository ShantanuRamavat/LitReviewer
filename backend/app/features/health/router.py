"""
Health endpoint router.

Exposes a single ``GET /health`` route that probes all downstream services
concurrently and returns a structured response indicating the overall system
health.

HTTP response codes:
- ``200 OK``           — all services are ``up`` (status: "healthy")
- ``503 Service Unavailable`` — at least one service is ``down`` (status: "degraded")

The response body always contains the full per-service breakdown, so
operators can identify which service is failing without reading application
logs.
"""

import asyncio

from fastapi import APIRouter, Depends, Response

from app.config import Settings, get_settings
from app.features.health import checks
from app.features.health.schemas import HealthResponse, HealthState, ServiceStatus

router = APIRouter(tags=["Health"])

# Application version is defined once here rather than duplicated across the
# codebase.  It will be moved to a shared constant or read from pyproject.toml
# in a future milestone.
_APP_VERSION = "1.0.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description=(
        "Probes all downstream services (PostgreSQL, Qdrant, Redis, Groq) "
        "concurrently and returns their individual status and latency. "
        "Returns HTTP 200 when all services are healthy, HTTP 503 when any "
        "service is degraded."
    ),
    responses={
        200: {"description": "All services are healthy."},
        503: {"description": "One or more services are unavailable."},
    },
)
async def health_check(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Run all service health checks concurrently and return a summary.

    Fires all four checks simultaneously using ``asyncio.gather`` so the
    endpoint latency equals the slowest individual check rather than their sum.

    Args:
        response: Injected Starlette response object, used to set the HTTP
            status code to 503 when the system is degraded.
        settings: Injected application settings.

    Returns:
        ``HealthResponse`` containing the aggregate status, application
        version, environment name, and per-service status details.
    """
    # Run all checks in parallel — do not short-circuit on first failure so
    # the response always contains the full picture.
    postgres_status, qdrant_status, redis_status, groq_status = await asyncio.gather(
        checks.check_postgres(),
        checks.check_qdrant(),
        checks.check_redis(),
        checks.check_groq(settings.groq_api_key.get_secret_value()),
    )

    services: dict[str, ServiceStatus] = {
        "postgres": postgres_status,
        "qdrant": qdrant_status,
        "redis": redis_status,
        "groq": groq_status,
    }

    all_healthy = all(svc.status.value == "up" for svc in services.values())
    overall = HealthState.HEALTHY if all_healthy else HealthState.DEGRADED

    # Set 503 on the response when degraded so load balancers and k8s
    # readiness probes act on the HTTP status code without parsing JSON.
    if overall == HealthState.DEGRADED:
        response.status_code = 503

    return HealthResponse(
        status=overall,
        version=_APP_VERSION,
        environment=settings.environment,
        services=services,
    )
