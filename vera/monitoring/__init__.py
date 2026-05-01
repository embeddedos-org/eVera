"""Production monitoring and alerting for eVera.

Provides in-memory metrics collection, deep health checks, and alerting.
"""

from vera.monitoring.metrics import MetricsCollector

# Singleton instance used across the application
metrics = MetricsCollector()

__all__ = ["MetricsCollector", "metrics"]
