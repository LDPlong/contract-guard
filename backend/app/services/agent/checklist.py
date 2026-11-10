"""审查清单加载（app/data/checklists/*.json）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.constants import ContractType
from app.core.errors import UnsupportedContractType

CHECKLIST_DIR = Path(__file__).resolve().parents[2] / "data" / "checklists"


@dataclass
class ChecklistItem:
    id: str
    name: str
    category: str
    keywords: list[str]
    query: str
    risk_rule: str
    legal_refs: list[str] = field(default_factory=list)
    weight: str = "medium"
    mode: str = "judge"  # judge | missing_check
    required_terms: list[str] = field(default_factory=list)


@dataclass
class Checklist:
    contract_type: str
    version: str
    items: list[ChecklistItem]

    def __len__(self) -> int:
        return len(self.items)


@lru_cache(maxsize=8)
def load_checklist(contract_type: str) -> Checklist:
    key = contract_type if contract_type != ContractType.UNKNOWN else ""
    if not key:
        raise UnsupportedContractType("暂不支持该合同类型")

    path = CHECKLIST_DIR / f"{key}.json"
    if not path.is_file():
        raise UnsupportedContractType(f"未找到 {key} 的审查清单")

    raw = json.loads(path.read_text(encoding="utf-8"))
    items = [ChecklistItem(**item) for item in raw["items"]]
    return Checklist(
        contract_type=raw["contract_type"],
        version=raw["version"],
        items=items,
    )
