"""FastAPI 应用入口。

职责：中间件、路由注册、异常处理、启动自检。
业务逻辑一律放 services/，本文件不得出现业务判断。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import documents, health
from app.core.config import get_settings
from app.core.constants import ErrorCode
from app.core.errors import BizError, ok
from app.core.logging import get_logger, request_id_ctx, setup_logging
from app.models.base import engine, init_models
from app.services.document_service import repair_stale_parsing

settings = get_settings()
log = get_logger(__name__)

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("DEBUG" if settings.app_env == "dev" else "INFO")
    settings.ensure_dirs()
    await init_models()
    await repair_stale_parsing()

    log.info(
        "app started env=%s demo_mode=%s ocr=%s llm_configured=%s workers_must_be_1=true",
        settings.app_env,
        settings.demo_mode,
        settings.ocr_enabled,
        settings.llm_configured,
    )
    if settings.demo_mode:
        log.warning("DEMO_MODE=true：所有审查结果来自本地兜底数据，不代表真实模型输出")

    yield

    await engine.dispose()
    log.info("app stopped")


app = FastAPI(
    title="ContractGuard",
    description="合同风险审查官 · 风险提示工具（非法律意见）",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Session-Id"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    token = request_id_ctx.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers["X-Request-Id"] = rid
    return response


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    log.warning("biz error code=%s msg=%s path=%s", exc.code, exc.message, request.url.path)
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    log.warning("validation error path=%s errors=%s", request.url.path, exc.errors()[:3])
    return JSONResponse(
        status_code=400,
        content={
            "code": int(ErrorCode.PARAM_INVALID),
            "message": "参数校验失败",
            "data": {"errors": exc.errors()[:5]},
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": int(ErrorCode.INTERNAL_ERROR),
            "message": "服务内部错误，请重试",
            "data": None,
        },
    )


@app.get("/")
async def root() -> dict:
    return ok({"name": "ContractGuard", "docs": "/docs", "health": f"{API_PREFIX}/health"})


app.include_router(health.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
