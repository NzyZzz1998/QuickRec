from __future__ import annotations

from dataclasses import replace

from services.timeline_drag_transaction import TimelineDragCandidate
from ui.timeline_drag_interaction import (
    TimelineDragInteraction,
    TimelineDragState,
)


def _candidate(transaction_id: str) -> TimelineDragCandidate:
    return TimelineDragCandidate.invalid(
        transaction_id=transaction_id,
        material_id="material-1",
        raw_start_us=0,
        start_us=0,
        conflict_code="test",
        conflict_reason="test candidate",
    )


def test_drag_interaction_uses_one_transaction_and_memory_candidate() -> None:
    interaction = TimelineDragInteraction(
        transaction_id_factory=lambda: "drag-1"
    )

    context = interaction.begin(
        material_id="material-1",
        has_video=True,
        has_audio=True,
        origin="project-materials",
    )
    updated = interaction.update(_candidate(context.transaction_id))

    assert interaction.state == TimelineDragState.DRAGGING
    assert context.transaction_id == "drag-1"
    assert updated
    assert interaction.candidate is not None
    assert interaction.context == context


def test_drag_interaction_rejects_stale_candidate_and_cancel_clears_state() -> None:
    interaction = TimelineDragInteraction(
        transaction_id_factory=lambda: "drag-current"
    )
    interaction.begin(
        material_id="material-1",
        has_video=True,
        has_audio=False,
        origin="project-materials",
    )

    assert not interaction.update(_candidate("drag-stale"))
    assert interaction.cancel()
    assert interaction.state == TimelineDragState.IDLE
    assert interaction.context is None
    assert interaction.candidate is None
    assert not interaction.cancel()


def test_drag_leave_and_finish_have_no_hidden_reuse() -> None:
    interaction = TimelineDragInteraction(
        transaction_id_factory=lambda: "drag-1"
    )
    context = interaction.begin(
        material_id="material-1",
        has_video=True,
        has_audio=False,
        origin="project-materials",
    )
    candidate = replace(
        _candidate(context.transaction_id),
        valid=True,
        conflict_code="",
        conflict_reason="",
    )
    assert interaction.update(candidate)

    finished = interaction.finish()

    assert finished == candidate
    assert interaction.state == TimelineDragState.IDLE
    assert interaction.finish() is None


def test_twenty_cancel_cycles_leave_no_candidate() -> None:
    counter = iter(f"drag-{index}" for index in range(20))
    interaction = TimelineDragInteraction(
        transaction_id_factory=lambda: next(counter)
    )

    for _ in range(20):
        context = interaction.begin(
            material_id="material-1",
            has_video=True,
            has_audio=True,
            origin="project-materials",
        )
        assert interaction.update(_candidate(context.transaction_id))
        assert interaction.cancel()

    assert interaction.state == TimelineDragState.IDLE
    assert interaction.candidate is None
