"""统一业务异常与响应包装。

接口契约（文档 8 节）：所有非 SSE 接口返回 {code, message, data}。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.constants import ERROR_HTTP_STATUS, ErrorCode

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": int(ErrorCode.OK), "message": message, "data": data}


class BizError(Exception):
    """可预期的业务异常，由全局处理器转成统一响应。"""

    def __init__(
        self,
        code: ErrorCode | int,
        message: str,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.detail = detail

    @property
    def http_status(self) -> int:
        return ERROR_HTTP_STATUS.get(self.code, 400)


class BadRequest(BizError):
    def __init__(self, message: str = "参数错误", detail: Any = None) -> None:
        super().__init__(ErrorCode.PARAM_INVALID, message, detail)


class UnsupportedFileType(BizError):
    def __init__(self, message: str = "文件类型不支持", detail: Any = None) -> None:
        super().__init__(ErrorCode.FILE_TYPE_UNSUPPORTED, message, detail)


class FileTooLarge(BizError):
    def __init__(self, message: str = "文件过大", detail: Any = None) -> None:
        super().__init__(ErrorCode.FILE_TOO_LARGE, message, detail)


class ParseFailed(BizError):
    def __init__(self, message: str = "解析失败", detail: Any = None) -> None:
        super().__init__(ErrorCode.PARSE_FAILED, message, detail)


class UnsupportedContractType(BizError):
    def __init__(self, message: str = "暂不支持该合同类型", detail: Any = None) -> None:
        super().__init__(ErrorCode.CONTRACT_TYPE_UNSUPPORTED, message, detail)


class LLMFailed(BizError):
    def __init__(self, message: str = "模型调用失败", detail: Any = None) -> None:
        super().__init__(ErrorCode.LLM_FAILED, message, detail)


class RetrieveEmpty(BizError):
    def __init__(self, message: str = "检索无结果", detail: Any = None) -> None:
        super().__init__(ErrorCode.RETRIEVE_EMPTY, message, detail)
