from __future__ import annotations

import copy

import pytest

from utils.schema_migrations import (
    SchemaMigrationError,
    SchemaMigrationRegistry,
    UnsupportedSchemaVersionError,
)


def test_current_schema_returns_an_isolated_payload_without_migration() -> None:
    registry = SchemaMigrationRegistry(
        label="project",
        current_version=1,
    )
    source = {
        "schema_version": 1,
        "extensions": {"future": {"enabled": True}},
    }

    result = registry.migrate(source)
    result.payload["extensions"]["future"]["enabled"] = False

    assert result.migrated is False
    assert result.source_version == result.target_version == 1
    assert result.steps == ()
    assert source["extensions"]["future"]["enabled"] is True


def test_registry_applies_contiguous_chain_and_preserves_source_payload() -> None:
    registry = SchemaMigrationRegistry(
        label="timeline",
        current_version=3,
    )
    registry.register(
        1,
        2,
        lambda payload: {
            **payload,
            "schema_version": 2,
            "tracks": payload.get("tracks", []),
        },
    )
    registry.register(
        2,
        3,
        lambda payload: {
            **payload,
            "schema_version": 3,
            "time_unit": "microseconds",
        },
    )
    source = {
        "schema_version": 1,
        "unknown": {"keep": True},
    }
    before = copy.deepcopy(source)

    result = registry.migrate(source)

    assert result.migrated is True
    assert result.source_version == 1
    assert result.target_version == 3
    assert result.steps == ((1, 2), (2, 3))
    assert result.payload["unknown"] == {"keep": True}
    assert result.payload["tracks"] == []
    assert result.payload["time_unit"] == "microseconds"
    assert source == before


def test_unknown_newer_schema_is_never_downgraded() -> None:
    registry = SchemaMigrationRegistry(
        label="project",
        current_version=2,
    )

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="newer than supported",
    ):
        registry.migrate({"schema_version": 99})


def test_missing_older_migration_path_is_rejected() -> None:
    registry = SchemaMigrationRegistry(
        label="timeline",
        current_version=3,
    )
    registry.register(
        2,
        3,
        lambda payload: {**payload, "schema_version": 3},
    )

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="migration path",
    ):
        registry.migrate({"schema_version": 1})


def test_registry_rejects_duplicate_or_non_contiguous_steps() -> None:
    registry = SchemaMigrationRegistry(
        label="project",
        current_version=3,
    )

    def migrate(payload):
        return {**payload, "schema_version": 2}

    registry.register(1, 2, migrate)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(1, 2, migrate)
    with pytest.raises(ValueError, match="contiguous"):
        registry.register(1, 3, migrate)


def test_migrator_must_return_expected_schema_version() -> None:
    registry = SchemaMigrationRegistry(
        label="project",
        current_version=2,
    )
    registry.register(1, 2, lambda payload: dict(payload))

    with pytest.raises(
        SchemaMigrationError,
        match="expected schema_version 2",
    ):
        registry.migrate({"schema_version": 1})


@pytest.mark.parametrize("schema_version", [None, True, "1", 1.5])
def test_schema_version_must_be_an_integer(schema_version: object) -> None:
    registry = SchemaMigrationRegistry(
        label="project",
        current_version=1,
    )

    with pytest.raises(SchemaMigrationError, match="integer"):
        registry.migrate({"schema_version": schema_version})
