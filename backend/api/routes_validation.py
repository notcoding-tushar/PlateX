"""Validation HTTP endpoints."""

from fastapi import APIRouter

from hosnt12.schemas import BenchmarkResult, H2Refinement, PaperValidationReport, PaperValidationRequest
from hosnt12.validation import (
    PAPER_TABLE_2_TSDT,
    PAPER_TABLE_3_TSDT,
    h2_stress_refinement,
    paper_validation_report,
    solve_paper_case,
)

router = APIRouter(prefix="/api", tags=["validation"])


@router.get("/validation")
def benchmark(hygrothermal: bool = False) -> BenchmarkResult:
    table = PAPER_TABLE_3_TSDT if hygrothermal else PAPER_TABLE_2_TSDT
    values = solve_paper_case(0, 0, 10, hygrothermal)
    names = ("w_bar", "sigma_x_bar", "tau_xy_bar", "tau_xz_bar")
    return BenchmarkResult(
        computed={name: values[name] for name in names}, reference=dict(zip(names, table[0, 0]))
    )


@router.post("/validation/suite")
def benchmark_suite(body: PaperValidationRequest) -> PaperValidationReport:
    return paper_validation_report(body)


@router.get("/validation/h2-refinement")
def benchmark_h2_refinement() -> H2Refinement:
    return h2_stress_refinement()
