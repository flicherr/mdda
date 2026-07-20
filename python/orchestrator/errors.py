class StandError(RuntimeError):
    """Base class for expected stand failures."""


class ManifestError(StandError):
    """A scenario manifest or its source tree is invalid."""


class ToolchainError(StandError):
    """The configured toolchain is unavailable or inconsistent."""


class ProcessFailure(StandError):
    """An infrastructure subprocess failed unexpectedly."""


class AnalyzerOutputError(StandError):
    """The C++ analyzer did not produce valid output."""

