"""测试全局配置：把数据库与存储目录指向临时路径，避免污染开发数据。

必须在导入 app.* 之前设置环境变量——engine 在模块导入时创建。
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

TMP_ROOT = Path(tempfile.mkdtemp(prefix="contractguard-test-"))

os.environ["DB_URL"] = f"sqlite+aiosqlite:///{(TMP_ROOT / 'test.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(TMP_ROOT / "uploads")
os.environ["INDEX_DIR"] = str(TMP_ROOT / "index")
os.environ["DEMO_MODE"] = "false"
os.environ["OCR_ENABLED"] = "false"

import pymupdf  # noqa: E402
import pytest  # noqa: E402

from app.models.base import init_models  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    asyncio.run(init_models())
    yield


def build_pdf_bytes(lines: list[str]) -> bytes:
    """生成一份最小可解析 PDF，用于上传接口测试。"""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 22
    data = doc.tobytes()
    doc.close()
    return data


def build_cn_pdf_bytes(lines: list[str]) -> bytes:
    """生成中文 PDF，条号与关键词都要能提取出来。"""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 90.0
    for line in lines:
        page.insert_text((72, y), line, fontname="china-s", fontsize=11)
        y += 22
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def chinese_pdf_bytes() -> bytes:
    return build_cn_pdf_bytes(
        [
            "房屋租赁合同",
            "第一条 甲方将位于某市某区的房屋出租给乙方。",
            "第二条 乙方逾期支付租金的，应当向甲方支付违约金。",
            "第三条 租赁期限为一年，租金每月三千元。",
        ]
    )


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    return build_pdf_bytes(
        [
            "Article 1 The landlord leases the house to the tenant.",
            "Article 2 The deposit equals one month rent.",
            "Article 3 The lease term is one year.",
        ]
    )
