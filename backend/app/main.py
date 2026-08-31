from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api import dashboard, exits, history, market, reconcile, returns, settings, slots, voyages
from app.api.common import failure, success
from app.core.config import get_config
from app.core.errors import DomainError
from app.db.init import init_db
from app.runtime import RuntimeContainer
from app.scheduler import MarketScheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    init_db(config=config)
    app.state.runtime = RuntimeContainer()
    app.state.scheduler = MarketScheduler(app.state.runtime)
    if config.scheduler_enabled and config.app_env.lower() != "test":
        app.state.scheduler.start()
    yield
    app.state.scheduler.shutdown()


app = FastAPI(title="CapitalVoyage API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (dashboard.router, slots.router, voyages.router, returns.router, exits.router, history.router, reconcile.router, market.router, settings.router):
    app.include_router(router)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    return failure(exc.code, exc.message, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {"msg": "请求参数无效"}
    return failure("INVALID_REQUEST", str(first.get("msg", "请求参数无效")), 422)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, _exc: SQLAlchemyError):
    return failure("DATABASE_ERROR", "数据库操作失败", 500)


@app.get("/api/health")
def health():
    return success({"status": "ok"})

