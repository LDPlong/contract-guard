"""全局常量：错误码、风险权重、超时与阈值。

约定：业务代码里不允许出现裸数字（magic number），统一引用本模块。
"""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """接口错误码，见文档 8 节错误码表。"""

    OK = 0
    PARAM_INVALID = 1001
    FILE_TYPE_UNSUPPORTED = 1002
    FILE_TOO_LARGE = 1003
    SESSION_INVALID = 1004
    PARSE_FAILED = 2001
    CONTRACT_TYPE_UNSUPPORTED = 2002
    TASK_IN_PROGRESS = 2003
    LLM_FAILED = 3001
    RETRIEVE_EMPTY = 3002
    RATE_LIMITED = 4290
    INTERNAL_ERROR = 5000  # 文档 8 节未覆盖的非预期异常，v1.2 待补入契约


# 错误码 -> HTTP 状态码
ERROR_HTTP_STATUS: dict[int, int] = {
    ErrorCode.OK: 200,
    ErrorCode.PARAM_INVALID: 400,
    ErrorCode.FILE_TYPE_UNSUPPORTED: 415,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.SESSION_INVALID: 400,
    ErrorCode.PARSE_FAILED: 422,
    ErrorCode.CONTRACT_TYPE_UNSUPPORTED: 422,
    ErrorCode.TASK_IN_PROGRESS: 202,
    ErrorCode.LLM_FAILED: 502,
    ErrorCode.RETRIEVE_EMPTY: 503,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.INTERNAL_ERROR: 500,
}


class RiskLevel(str):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ContractType(str):
    LEASE = "lease"
    LABOR = "labor"
    PREPAID = "prepaid"
    UNKNOWN = "unknown"


SUPPORTED_CONTRACT_TYPES = (
    ContractType.LEASE,
    ContractType.LABOR,
    ContractType.PREPAID,
)

SUPPORTED_MIME_TYPES = (
    "application/pdf",
    "image/jpeg",
    "image/png",
)

# ---- 安全分算法（文档 10.2，固定，不交给模型）----
SCORE_BASE = 100
SCORE_DEDUCT = {
    RiskLevel.HIGH: 12,
    RiskLevel.MEDIUM: 5,
    RiskLevel.LOW: 2,
}
SCORE_MISSING_ITEM_DEDUCT = 8
SCORE_MIN = 0
SCORE_MAX = 100

# ---- Agent 预筛与并发（文档 10.1 / 10.3）----
GATE_TOP_K = 5
GATE_MIN_SCORE = 3.0
JUDGE_TIMEOUT_SEC = 25
LLM_MAX_CONCURRENCY = 3

# ---- 检索（文档 7.2）----
RRF_K = 60
RETRIEVE_TIMEOUT_MS = 800

# ---- 解析（文档 3.4 / 8.1）----
PARSE_TIMEOUT_SEC = 10
STALE_PARSING_MINUTES = 5
MAX_FILE_MB = 20
MAX_PAGES = 80
