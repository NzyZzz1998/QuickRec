from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any


class CliExitCode(IntEnum):
    SUCCESS = 0
    USAGE_ERROR = 2
    VALIDATION_FAILED = 3
    DEPENDENCY_MISSING = 4
    TIMEOUT = 5
    CANCELLED = 6
    ISOLATION_ERROR = 7
    INTERNAL_ERROR = 8


class CliStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class CliIdentity:
    product: str
    version: str
    frozen: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "version": self.version,
            "frozen": self.frozen,
        }


@dataclass(frozen=True)
class CliError:
    category: str
    message: str
    context: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "message": self.message,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class CliReport:
    command: str
    status: CliStatus
    exit_code: CliExitCode
    started_at: str
    duration_ms: int
    identity: CliIdentity
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[CliError] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "command": self.command,
            "status": self.status.value,
            "exit_code": int(self.exit_code),
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "identity": self.identity.to_dict(),
            "result": dict(self.result),
            "errors": [error.to_dict() for error in self.errors],
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class CliCommandOutcome:
    result: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


class CliFailure(RuntimeError):
    def __init__(
        self,
        exit_code: CliExitCode,
        category: str,
        message: str,
        *,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.category = category
        self.message = message
        self.context = dict(context or {})

    def to_error(self) -> CliError:
        return CliError(self.category, self.message, self.context)


def status_for_exit_code(exit_code: CliExitCode) -> CliStatus:
    if exit_code == CliExitCode.SUCCESS:
        return CliStatus.SUCCESS
    if exit_code == CliExitCode.TIMEOUT:
        return CliStatus.TIMEOUT
    if exit_code == CliExitCode.CANCELLED:
        return CliStatus.CANCELLED
    return CliStatus.FAILED
