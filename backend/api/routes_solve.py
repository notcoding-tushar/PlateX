from fastapi import APIRouter

from hosnt12.schemas import (
    AnalysisConfig,
    AnalysisResult,
    SweepRequest,
)
from hosnt12.solver import solve_hosnt12, solve_sweep

router = APIRouter(prefix="/api")


@router.post("/solve")
def solve(config: AnalysisConfig) -> AnalysisResult:
    return solve_hosnt12(config, include_field=True)


@router.post("/solve-sweep")
def sweep(body: SweepRequest) -> list[AnalysisResult]:
    return solve_sweep(body.base_config, body.load_cases, include_field=True)

