"""starloader: a small, dependency-free toolkit for loading CSV extracts into a
SQLite star schema (dimensions with SCD Type 2 history, incremental facts,
data quality checks and a date dimension)."""

from starloader.config import PipelineConfig, load_config
from starloader.pipeline import Pipeline, RunResult

__all__ = ["PipelineConfig", "load_config", "Pipeline", "RunResult"]
__version__ = "0.3.0"
