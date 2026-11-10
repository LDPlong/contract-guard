"""检索冒烟：跑一组典型审查查询，人工看 Top3 是否命中目标条文。

用法：
    python -m scripts.retrieval_smoke

口径：命中判定按"法规名 + 条号"，因为不同法的条号会撞（民法典第 35 条 ≠ 民诉法第 35 条）。
"""

from __future__ import annotations

import asyncio

from app.services.rag.retriever import Retriever

# (查询词, 期望命中集合)  —— 空集合表示知悉项：只看召回，不计命中
CASES: list[tuple[str, set[str]]] = [
    ("租赁期限届满 返还 租赁物", {"民法典 第七百三十三条"}),
    ("试用期 期限 六个月 上限", {"劳动合同法 第十九条"}),
    ("竞业限制 期限 二年 补偿", {"劳动合同法 第二十三条", "劳动合同法 第二十四条"}),
    ("转租 未经同意 解除合同", {"民法典 第七百一十六条"}),
    ("违约金 过高 调整", {"民法典 第五百八十五条"}),
    ("解除合同 不可抗力", {"民法典 第五百六十三条"}),
    ("押金 退还 期限", set()),  # 知悉项：民法典未直接规定押金，观察实际召回
    ("协议管辖 书面 约定 人民法院", {"民事诉讼法 第三十五条"}),
    ("格式条款 排除 限制 消费者权利", {"消费者权益保护法 第二十六条"}),
    ("消费者 自主选择 商品 服务", {"消费者权益保护法 第九条"}),
    ("用人单位 三十日 社会保险 登记", {"社会保险法 第五十八条"}),
]


async def main() -> None:
    retriever = Retriever()
    print(f"chunks={retriever.chunk_count} vector_channel={retriever.has_vector_channel}\n")

    hit = 0
    for query, expected in CASES:
        results = await retriever.search(query, top_k=3)
        got = {f"{r.source} {r.article_no}" for r in results}
        ok = bool(expected & got) if expected else None
        hit += int(bool(ok))
        mark = "·" if ok is None else ("✓" if ok else "✗")
        print(f"{mark} {query}")
        for item in results:
            print(f"    {item.score:.5f}  {item.article_no:<10} ({item.source}) {item.content[:40]}")
        print()

    scored = [c for c in CASES if c[1]]
    print(f"Top3 命中 {hit}/{len(scored)}")


if __name__ == "__main__":
    asyncio.run(main())
