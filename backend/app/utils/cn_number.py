"""中文数字与整数互转（法条编号专用）。

放在 utils 里给脚本和接口共用：语料导入需要它判断条号，
接口需要按条号整数排序（字符串排序会把"第十条"排在"第二条"前面）。
"""

from __future__ import annotations

DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
          "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
UNITS = {"十": 10, "百": 100, "千": 1000}
CN = "零一二三四五六七八九"
CN_UNIT_POS = ["", "十", "百", "千"]


def cn_to_int(text: str) -> int | None:
    """中文数字转整数，支持 1~9999。非法字符返回 None。"""
    total, section, number = 0, 0, 0
    for ch in text:
        if ch in DIGITS:
            number = DIGITS[ch]
        elif ch in UNITS:
            section += (number or 1) * UNITS[ch]
            number = 0
        else:
            return None
    return total + section + number


def number_to_cn(number: int) -> str:
    """整数转中文条号：716 → 七百一十六，16 → 十六，1105 → 一千一百零五。"""
    if number <= 0:
        return CN[0]

    raw = str(number)
    parts: list[str] = []
    pending_zero = False
    for idx, ch in enumerate(raw):
        digit = int(ch)
        pos = len(raw) - idx - 1
        if digit == 0:
            pending_zero = True
            continue
        if pending_zero and parts:
            parts.append("零")
        pending_zero = False
        parts.append(CN[digit] + CN_UNIT_POS[pos])

    text = "".join(parts)
    if text.startswith("一十"):
        text = text[1:]
    return text
