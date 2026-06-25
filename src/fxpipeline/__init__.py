"""fxpipeline: a small, production-style ELT pipeline for foreign-exchange rates.

Extract daily currency rates from the free Frankfurter API, transform them with
pandas into a tidy/long format (with daily percentage change and moving
averages), and load them idempotently into a local DuckDB warehouse.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
