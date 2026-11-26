from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import routes_irc, routes_solve, routes_validation
from .config import cors_origins


def create_app() -> FastAPI:
    app = FastAPI(title="PlateX · HOSNT12", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(routes_solve.router)
    app.include_router(routes_irc.router)
    app.include_router(routes_validation.router)

    @app.exception_handler(ValueError)
    @app.exception_handler(RuntimeError)
    async def analysis_error(request: Request, exc: Exception):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
