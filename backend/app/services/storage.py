"""上传落盘与文件校验。

安全约定（文档 14 节）：
- 类型判断用 magic number，不看扩展名
- 落盘文件名一律用 uuid，**用户提供的文件名只作展示**
- 读取时按分块累计，超限立即中断，不把超大文件读进内存
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.constants import MAX_FILE_MB
from app.core.errors import FileTooLarge, UnsupportedFileType

READ_CHUNK = 1024 * 256

# magic number → (mime, 扩展名)
SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
]


@dataclass
class SavedFile:
    stored_name: str
    file_path: Path
    mime_type: str
    size_bytes: int
    sha256: str


def sniff(head: bytes) -> tuple[str, str] | None:
    """按文件头判定类型，返回 (mime, ext)；未识别返回 None。"""
    for magic, mime, ext in SIGNATURES:
        if head.startswith(magic):
            return mime, ext
    return None


async def save_upload(upload_file, max_mb: int = MAX_FILE_MB) -> SavedFile:
    """把上传流写到磁盘，同时算 sha256。

    先写临时文件再改名，避免半截文件被当成有效合同。
    """
    settings = get_settings()
    settings.ensure_dirs()

    head = await upload_file.read(len(b"%PDF-"))
    detected = sniff(head)
    if detected is None:
        # 需要更多字节时补读一次，覆盖 JPEG/PNG 更长的头
        more = await upload_file.read(16)
        detected = sniff(head + more)
        head += more
    if detected is None:
        raise UnsupportedFileType("仅支持 PDF / JPG / PNG，且需为真实文件（扩展名不作为依据）")

    mime_type, ext = detected
    stored_name = f"{uuid.uuid4().hex}{ext}"
    target = settings.upload_path / stored_name
    tmp = target.with_suffix(target.suffix + ".part")

    digest = hashlib.sha256()
    size = 0
    limit = max_mb * 1024 * 1024

    try:
        with tmp.open("wb") as fp:
            fp.write(head)
            digest.update(head)
            size += len(head)
            while True:
                chunk = await upload_file.read(READ_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise FileTooLarge(f"文件超过 {max_mb}MB 上限")
                fp.write(chunk)
                digest.update(chunk)
        tmp.replace(target)
    except Exception:
        tmp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise

    if size == 0:
        target.unlink(missing_ok=True)
        raise UnsupportedFileType("文件内容为空")

    return SavedFile(
        stored_name=stored_name,
        file_path=target,
        mime_type=mime_type,
        size_bytes=size,
        sha256=digest.hexdigest(),
    )


def remove_saved_file(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
