"""
Pydantic response models for the health endpoint.

The ``HealthResponse`` model provides both a machine-readable overall status
(``healthy`` | ``degraded``) and per-service detail including round-trip
latency in milliseconds.  This allows load balancers to act on the HTTP status
code while operators can inspect the JSON body for root-cause information.

Example response (all services up)::

    {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "development",
        "services": {
            "postgres": {"status": "up", "latency_ms": 3.4},
            "qdrant":   {"status": "up", "latency_ms": 8.1},
            "redis":    {"status": "up", "latency_ms": 1.2},
            "groq":     {"status": "up", "latency_ms": 0.0}
        }
    }

Example response (one service down)::

    {
        "status": "degraded",
        ...
        "services": {
            "postgres": {"status": "down", "error": "Connection refused"}
            ...
        }
    }
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ServiceState(StrEnum):
    """Operational state of an individual downstream service."""

    UP = "up"
    DOWN = "down"


class HealthState(StrEnum):
    """Aggregate health state of the application.

    ``HEALTHY``  — all checked services are ``up``.
    ``DEGRADED`` — at least one service is ``down``; the API returns HTTP 503.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"


class ServiceStatus(BaseModel):
    """Health status and latency for a single downstream service.

    Attributes:
        status: Whether the service responded successfully.
        latency_ms: Round-trip time in milliseconds, if the check succeeded.
        error: Short error message if the service is ``down``.
    """

    status: ServiceState
    latency_ms: float | None = Field(
        default=None,
        description="Round-trip latency in milliseconds.",
        examples=[4.2],
    )
    error: str | None = Field(
        default=None,
        description="Error message when status is 'down'.",
        examples=["Connection refused"],
    )


class HealthResponse(BaseModel):
    """Full health check response returned by GET /health.

    Attributes:
        status: Aggregate status — ``healthy`` if all services are up,
            ``degraded`` otherwise.
        version: Application version string.
        environment: Runtime environment name (development / staging / production).
        services: Mapping of service name → its individual ``ServiceStatus``.
    """

    status: HealthState = Field(description="Aggregate application health.")
    version: str = Field(description="Application version.", examples=["1.0.0"])
    environment: str = Field(
        description="Runtime environment.",
        examples=["development"],
    )
    services: dict[str, ServiceStatus] = Field(
        description="Per-service health status and latency.",
    )
