# 前端修复记录（2026-11）

> 范围：`frontend/` 的可用性与一致性修复，外加一处后端数据契约修复。
> 结论先行：**这一轮最值钱的不是样式，是修好了「结论 ↔ 原文」的断联。**

---

## 一、改了什么

### P0 · 会让功能看起来坏掉的

| 问题 | 文件 | 做法 |
| --- | --- | --- |
| 390px 下顶栏按钮被压成竖排单字 | `views/ReviewView.vue` | 动作区改 `flex-wrap`；按钮加 `shrink-0 whitespace-nowrap`；<640px 两个按钮降级为图标（保留 `aria-label`） |
| 移动端「原版」PDF 横向溢出 | `components/ClauseViewer.vue` | 缩放下限 `460 → 260`。460 比 390 屏的容器还宽，是溢出的直接原因；小屏不再自动切到原版 |
| 手机首屏先给合同封面，结论在第二屏之后 | `views/ReviewView.vue` | 两栏加 `order-1 / lg:order-2`，只改顺序不动 DOM |
| 次要文字对比度 3.11:1 | `tailwind.config.js` | `ink.faint` `#8A8F98 → #6B7078`（paper 底 4.77:1）；新增 `ink.ghost #9AA0A8` 专供装饰；`risk.medium` `#A96A00 → #8F5A00`（5.78:1） |
| 正文字号偏小 | `styles/main.css`、`FindingPanel.vue`、`ClauseViewer.vue` | `.label` 10→11；结论卡标题 14→15、原因 12→13.5、法条 11→12；原文条款 12.5→**15** |

### P1 · 信息层级

| 问题 | 做法 |
| --- | --- |
| 命中条款按模型返回顺序排 | `clauseOrdinal()` 解析「第三条 / 第11条 / 第十一条」为数字后排序，解析不出排最后 |
| 审查跑完了仍占 190px | `AgentTrace.vue` 完成后自动折成一行，可展开回看 |
| 每张结论卡末尾都有「仅提示风险，不构成法律意见」 | 删掉卡内那行，只留页脚与报告页脚 |
| **法条依据埋在二级展开里** | 折叠态加一行 `依据　民法典 第七百三十三条 +1`；展开区标题改为「法条原文」避免重复 |
| 多张卡可同时展开，列表变成信息瀑布 | 改手风琴，同时只展一张 |
| 右下「问」浮球压住结论卡 | 状态提到全局 store，审查页把入口内联到右栏底部「就这份合同提问」 |
| 手机 chips 占三行 | 默认给 4 个 + 「还有 N 条」，点开全展开；桌面端始终全显 |

### P2 · 观感

- 「条款/原版」分段控件：0 圆角 → 2px，字号 10→11，加 `min-h-28px`
- 主按钮：纯黑 → 藏青 `#1B3A6B`（hover `#12294D`），全站只留一个重色
- chip 触控目标：手机端 32px；tooltip 移动端隐藏（无 hover）、最后一个 chip 向右翻转防溢出
- PDF 首屏定位：不再停在封面

---

## 二、复盘：结论和原文一直是断联的

### 症状

页面看起来完全正常——结论卡、chips、原文都在。但：

- 原文里**从来没有出现过风险高亮**
- 点 chips 不会定位，点结论卡也不会跳到对应条款

不报错、不白屏，所以肉眼看不出来。

### 根因

两套 ID 各玩各的：

| 来源 | clause_id 形态 |
| --- | --- |
| 工作流内部（SSE 推过来的） | `c11` / `c4` / `c10` —— `c{seq}` 内部 key |
| 数据库 / `document.clauses[].id` | UUID `60b4dddf…` |

`_persist_result` 落库时做了映射（`clause_id_by_seq`），但 **SSE 出口直接透传了原始 key**，前端拿到的是 `c{seq}`，跟 `clause.id` 永远不相等。于是所有依赖 `highlights[clause.id]` 的地方全部静默失效。

### 修法

`backend/app/services/review_service.py`，在 SSE 出口统一转换：

```python
def _db_clause_id(value, clause_id_by_seq: dict[int, str]) -> str | None:
    if isinstance(value, str) and len(value) > 1 and value[0] == "c" and value[1:].isdigit():
        return clause_id_by_seq.get(int(value[1:]))
    return value if isinstance(value, str) else None
```

作用点两处：

1. `event == "finding"` 的帧
2. `event == "done"` 里的 `payload["findings"]`（不补这里，流式期间正确、收尾时又被打回原样）

### 验证

```bash
curl -sN -X POST -H "X-Session-Id: demo" \
  "http://127.0.0.1:8000/api/v1/documents/<doc_id>/review" -o /tmp/sse.txt
```

```python
# 6 条结论的 clause_id 应当全是 UUID
272442c1…  第十条   13af6002…  第三条   14e6cafd…  第九条
db0f17ce…  第七条   5a903446…  第一条   e37ed7ce…  第十一条
```

```js
// 页面侧：16 条条款里应当有 6 条带风险色边，与 6 条结论一一对应
[...document.querySelectorAll('div[data-clause-id]')]
  .filter(n => !/229, 226, 218|0, 0, 0, 0/.test(getComputedStyle(n).borderLeftColor)).length
// → 6
```

### 下次别踩的坑

**统计高亮时不要用 `[data-clause-id]`。** 这个属性同时挂在「原文段落 div」和「PDF 叠层 bbox 按钮」上，两类节点混在一起数，会得出「只亮 1 条」的错误结论（本轮在这个坑里浪费了一轮）。要按 `div[data-clause-id]` 过滤。

---

## 三、没做的

| 项 | 原因 |
| --- | --- |
| P2-03 边框过多 | 属整体气质调整。要撤掉卡片边框、改用底色分层，必须连同间距体系一起重排；单独改一两处会比现在更乱 |
| 画布 03 / 07 的三档样式 | Ardot 画布通道在当时的会话里不可用。改动清单在 `docs/ardot-fix-03-07.md`，能连上时直接执行 |

---

## 四、怎么跑起来验证

```bash
# 后端（演示模式，不需要 key）
cd backend && DEMO_MODE=true .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端
cd frontend && npm run dev -- --port 5199
```

打开 `/review/<doc_id>?sid=demo` 即可。所有改动均已 `npm run build`（`vue-tsc --noEmit && vite build`）通过。
