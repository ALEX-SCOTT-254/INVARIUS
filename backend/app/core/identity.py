"""Application identity for INVARIUS."""

from dataclasses import dataclass

from .version import __phase__, __release__, __version__


@dataclass(frozen=True)
class ApplicationIdentity:
    """Immutable identity information for the running application."""

    name: str
    version: str
    phase: str
    release: str


APPLICATION_IDENTITY = ApplicationIdentity(
    name="INVARIUS",
    version=__version__,
    phase=__phase__,
    release=__release__,
)
