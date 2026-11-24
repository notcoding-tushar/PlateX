from fastapi import APIRouter

from hosnt12.irc import adapters
from hosnt12.schemas import (
    AnalysisResult,
    CatalogueOptions,
    IRCCheck,
    IRCClimateOptions,
    IRCClimateRequest,
    IRCClimateResult,
    IRCComplianceRequest,
    IRCComplianceResult,
    IRCFlexibleRequest,
    IRCFoundationLookup,
    IRCOption,
    IRCPlacement,
    IRCPrepared,
    IRCPreview,
    IRCRigidRequest,
    IRCSweepRequest,
    LayeredElasticRequest,
    LayeredElasticResult,
)
from hosnt12.solver import solve_hosnt12

router = APIRouter(prefix="/api/irc")


@router.get("/climate-options")
def climate_options() -> IRCClimateOptions:
    return adapters.climate_options()


@router.post("/climate-temperature")
def climate_temperature(body: IRCClimateRequest) -> IRCClimateResult:
    return adapters.climate_temperature(body)


@router.get("/options")
def options() -> list[IRCOption]:
    return adapters.options()


@router.post("/preview-loads")
def preview(body: IRCPlacement) -> IRCPreview:
    return adapters.preview_loads(body)


@router.post("/check")
def check(body: IRCPlacement) -> list[IRCCheck]:
    return adapters.check(body)


@router.post("/rigid")
def rigid(body: IRCRigidRequest) -> IRCPrepared:
    return adapters.prepare_rigid(body)


@router.post("/foundation-lookup")
def foundation_lookup(body: IRCFoundationLookup) -> dict:
    return adapters.foundation_lookup(body)


@router.post("/flexible")
def flexible(body: IRCFlexibleRequest) -> IRCPrepared:
    return adapters.prepare_flexible(body)


@router.get("/flexible/catalogue-options")
def catalogue_options() -> CatalogueOptions:
    return adapters.catalogue_options()


@router.post("/flexible/layered-elastic")
def flexible_layered(body: LayeredElasticRequest) -> LayeredElasticResult:
    return adapters.solve_flexible_layered(body)


@router.post("/compliance")
def compliance(body: IRCComplianceRequest) -> IRCComplianceResult:
    return adapters.compliance(body)


@router.get("/bridge-guidance")
def bridge_guidance(width_m: float, vehicle: str = "A") -> dict:
    return adapters.bridge_guidance(width_m, vehicle)


@router.post("/solve")
def solve(body: IRCPrepared) -> AnalysisResult:
    result = solve_hosnt12(body.config, include_field=True)
    result.modeling_notes.extend(body.modeling_notes)
    result.sources.extend(body.sources)
    return result


@router.post("/sweep")
def sweep(body: IRCSweepRequest) -> list[AnalysisResult]:
    return adapters.solve_placements(body.base_config, body.placements)
