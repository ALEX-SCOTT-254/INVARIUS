from datetime import datetime, timezone

import pytest

from backend.app.core.errors import InvariusError, ValidationError
from backend.app.core.evidence import Evidence, EvidenceState
from backend.app.core.result import (
    RESULT_CONTRACT_VERSION,
    Result,
    ResultStatus,
)


def make_evidence() -> Evidence:
    return Evidence(
        state=EvidenceState.FACT,
        statement="The source file exists.",
        source="repository",
        confidence=1.0,
        observed_at=datetime(
            2026,
            9,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_result_success() -> None:
    result = Result(
        status=ResultStatus.SUCCESS,
        value={"files": 10},
    )

    assert result.status == ResultStatus.SUCCESS
    assert result.value == {"files": 10}
    assert result.contract_version == RESULT_CONTRACT_VERSION


def test_result_partial() -> None:
    evidence = make_evidence()

    result = Result(
        status=ResultStatus.PARTIAL,
        value={"files": 8},
        evidence=(evidence,),
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.value == {"files": 8}
    assert result.evidence == (evidence,)


def test_result_failure() -> None:
    error = InvariusError(
        "Source could not be accessed.",
        code="SOURCE_ACCESS_ERROR",
    )

    result = Result(
        status=ResultStatus.FAILURE,
        errors=(error,),
    )

    assert result.status == ResultStatus.FAILURE
    assert result.errors == (error,)


def test_result_unresolved() -> None:
    evidence = make_evidence()

    result = Result(
        status=ResultStatus.UNRESOLVED,
        evidence=(evidence,),
    )

    assert result.status == ResultStatus.UNRESOLVED
    assert result.evidence == (evidence,)


def test_result_is_immutable() -> None:
    result = Result(
        status=ResultStatus.SUCCESS,
        value="complete",
    )

    with pytest.raises(AttributeError):
        result.status = ResultStatus.FAILURE  # type: ignore[misc]


def test_evidence_must_be_tuple() -> None:
    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.SUCCESS,
            evidence=[make_evidence()],  # type: ignore[arg-type]
        )


def test_evidence_must_contain_evidence_objects() -> None:
    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.SUCCESS,
            evidence=("not evidence",),  # type: ignore[arg-type]
        )


def test_errors_must_be_tuple() -> None:
    error = InvariusError("Failure.")

    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.FAILURE,
            errors=[error],  # type: ignore[arg-type]
        )


def test_errors_must_contain_invarius_errors() -> None:
    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.FAILURE,
            errors=("not an error",),  # type: ignore[arg-type]
        )


def test_empty_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.SUCCESS,
            contract_version="   ",
        )


def test_non_string_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Result(
            status=ResultStatus.SUCCESS,
            contract_version=123,  # type: ignore[arg-type]
        )


def test_invalid_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Result(
            status="success",  # type: ignore[arg-type]
        )
