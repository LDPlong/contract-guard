"""图片合同解析测试（多模态通道）。"""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from app.services.llm.client import LLMClient
from app.services.parsing.vision_parser import parse_image


@pytest.fixture()
def sample_png(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=240)
    page.insert_text((30, 40), "房屋租赁合同", fontname="china-s", fontsize=11)
    page.insert_text((30, 70), "第一条 甲方将房屋出租给乙方。", fontname="china-s", fontsize=11)
    pix = page.get_pixmap(dpi=120)
    path = tmp_path / "contract.png"
    path.write_bytes(pix.tobytes("png"))
    doc.close()
    return path


def fake_client(payload: dict | str) -> LLMClient:
    body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

    async def transport(messages, json_mode, max_tokens):
        # 断言确实把图片送进去了
        assert isinstance(messages[1]["content"], list)
        assert any(part.get("type") == "image_url" for part in messages[1]["content"])
        return body, {"prompt_tokens": 10, "completion_tokens": 5}, "fake-vision"

    return LLMClient(transport=transport)


@pytest.mark.asyncio
async def test_parse_image_builds_clauses(sample_png):
    payload = {
        "contract_type": "lease",
        "clauses": [
            {"clause_no": "第一条", "text": "甲方将房屋出租给乙方。"},
            {"clause_no": "第二条", "text": "押金为一个月租金。"},
            {"clause_no": None, "text": "本合同一式两份。"},
        ],
    }
    result = await parse_image(sample_png, client=fake_client(payload))

    assert result.contract_type == "lease"
    assert len(result.clauses) == 3
    assert [c.seq for c in result.clauses] == [1, 2, 3]
    assert result.clauses[0].clause_no == "第一条"
    assert result.clauses[2].clause_no is None
    assert result.clauses[0].bbox is None  # 图片没有坐标
    assert result.full_text.startswith("甲方将房屋出租给乙方。")


@pytest.mark.asyncio
async def test_char_offsets_follow_full_text(sample_png):
    payload = {
        "contract_type": "lease",
        "clauses": [
            {"clause_no": "第一条", "text": "短条款。"},
            {"clause_no": "第二条", "text": "另一条款。"},
        ],
    }
    result = await parse_image(sample_png, client=fake_client(payload))

    for clause in result.clauses:
        assert result.full_text[clause.char_start : clause.char_end] == clause.text


@pytest.mark.asyncio
async def test_invalid_json_raises(sample_png):
    with pytest.raises(ValueError):
        await parse_image(sample_png, client=fake_client("这张图看不清"))


@pytest.mark.asyncio
async def test_empty_clauses_raises(sample_png):
    with pytest.raises(ValueError):
        await parse_image(sample_png, client=fake_client({"contract_type": "lease", "clauses": []}))


@pytest.mark.asyncio
async def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        await parse_image(tmp_path / "nope.png", client=fake_client({"clauses": []}))
