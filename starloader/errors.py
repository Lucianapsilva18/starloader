class StarloaderError(Exception):
    """Base class for all starloader errors."""


class ConfigError(StarloaderError):
    """Invalid or incomplete pipeline configuration."""


class ExtractError(StarloaderError):
    """A source file could not be read or a value could not be coerced."""


class QualityError(StarloaderError):
    """One or more blocking data quality rules failed."""

    def __init__(self, report):
        self.report = report
        super().__init__(report.summary())
