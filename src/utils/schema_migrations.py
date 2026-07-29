from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SchemaPayload = dict[str, Any]
SchemaMigrator = Callable[[SchemaPayload], SchemaPayload]


class SchemaMigrationError(ValueError):
    pass


class UnsupportedSchemaVersionError(SchemaMigrationError):
    pass


@dataclass(frozen=True)
class SchemaMigrationResult:
    payload: SchemaPayload
    source_version: int
    target_version: int
    steps: tuple[tuple[int, int], ...] = ()

    @property
    def migrated(self) -> bool:
        return bool(self.steps)


@dataclass(frozen=True)
class _MigrationStep:
    from_version: int
    to_version: int
    migrate: SchemaMigrator


class SchemaMigrationRegistry:
    def __init__(self, *, label: str, current_version: int) -> None:
        normalized_label = str(label).strip()
        if not normalized_label:
            raise ValueError("schema label is required")
        if (
            not isinstance(current_version, int)
            or isinstance(current_version, bool)
            or current_version < 1
        ):
            raise ValueError("current_version must be a positive integer")
        self.label = normalized_label
        self.current_version = current_version
        self._steps: dict[int, _MigrationStep] = {}

    def register(
        self,
        from_version: int,
        to_version: int,
        migrator: SchemaMigrator,
    ) -> None:
        if to_version != from_version + 1:
            raise ValueError("schema migration steps must be contiguous")
        if from_version in self._steps:
            raise ValueError(
                f"migration from schema {from_version} is already registered"
            )
        self._steps[from_version] = _MigrationStep(
            from_version,
            to_version,
            migrator,
        )

    def migrate(self, payload: SchemaPayload) -> SchemaMigrationResult:
        current_payload = copy.deepcopy(payload)
        source_version = self._read_version(current_payload)
        if source_version > self.current_version:
            raise UnsupportedSchemaVersionError(
                f"{self.label} schema {source_version} is newer than "
                f"supported schema {self.current_version}"
            )

        version = source_version
        applied: list[tuple[int, int]] = []
        while version < self.current_version:
            step = self._steps.get(version)
            if step is None:
                raise UnsupportedSchemaVersionError(
                    f"no {self.label} migration path from schema "
                    f"{version} to {self.current_version}"
                )
            try:
                migrated = step.migrate(copy.deepcopy(current_payload))
            except SchemaMigrationError:
                raise
            except Exception as exc:
                raise SchemaMigrationError(
                    f"{self.label} migration {step.from_version}->"
                    f"{step.to_version} failed: {exc}"
                ) from exc
            if not isinstance(migrated, dict):
                raise SchemaMigrationError(
                    f"{self.label} migration {step.from_version}->"
                    f"{step.to_version} must return an object"
                )
            actual_version = self._read_version(migrated)
            if actual_version != step.to_version:
                raise SchemaMigrationError(
                    f"{self.label} migration {step.from_version}->"
                    f"{step.to_version} expected schema_version "
                    f"{step.to_version}, received {actual_version}"
                )
            current_payload = copy.deepcopy(migrated)
            version = step.to_version
            applied.append((step.from_version, step.to_version))

        return SchemaMigrationResult(
            payload=current_payload,
            source_version=source_version,
            target_version=version,
            steps=tuple(applied),
        )

    def _read_version(self, payload: SchemaPayload) -> int:
        version = payload.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise SchemaMigrationError(
                f"{self.label} schema_version must be an integer"
            )
        return version
