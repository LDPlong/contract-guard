# ContractGuard · 合同风险审查官

上传一份合同，逐条标出高风险条款，给出法条依据与可谈的修改方向。

> **本工具仅提供风险提示与修改方向，不构成法律意见，不替代执业律师。**

面向个人（租房青年、实习生、应届生）的合同风险提示工具，只覆盖三类合同：
房屋租赁、实习/劳动合同、培训贷/预付卡。

---

## 当前进度

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、健康检查、前端首页 | ✅ 完成 |
| M1 | PDF 解析 + 条款切分 + bbox 定位 | ⬜ 待开始 |
| M2 | pdf.js 双栏审查台 | ⬜ |
| M3 | 法规语料入库 + 检索 | ⬜ |
| M4 | Agent 工作流 + SSE | ⬜ |
| M5 | 高亮联动 | ⬜ |
| M6 | 安全分 + 报告导出 | ⬜ |
| M7 | 脱敏 / 限流 / 兜底 | ⬜ |
| M8 | 交付材料 | ⬜ |

规格文档：[`docs/项目开发文档.md`](docs/项目开发文档.md)（v1.1，实现以此为准）

---

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Tailwind CSS + Pinia + pdf.js
- **后端**：Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / PyMuPDF
- **检索**：BM25 + numpy 向量 + RRF 融合（不引入向量库，见文档 3.2 选型说明）
- **模型**：OpenAI 兼容协议，通过 `services/llm/client.py` 统一调用

---

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt -r requirements-dev.txt
copy ..\.env.example ..\.env    # 填入 LLM_API_KEY
uvicorn app.main:app --reload --port 8000 --workers 1
```

> 国内网络建议加 `-i https://mirrors.aliyun.com/pypi/simple`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

前端通过 Vite 代理把 `/api` 转发到 `http://127.0.0.1:8000`。

### 3. 验证

```bash
curl http://127.0.0.1:8000/api/v1/health
```

```json
{"status":"ok","db":true,"vector":false,"index_built":false,"llm":true,"demo_mode":false}
```

`vector=false` 表示法规索引尚未构建（M3 完成 `scripts/build_index.py` 后为 true）。

---

## 运行时约束（违反会导致状态错乱）

1. **uvicorn 必须 `--workers 1`**
   解析任务、SSE 连接状态、BM25 内存索引都驻留在单进程内，多 worker 会导致任务丢失与索引不一致。

2. **SQLite 自动开 WAL + 外键**
   代码在连接时执行 `PRAGMA journal_mode=WAL; foreign_keys=ON`，否则 SSE 长连接期间写 findings 会 `database is locked`，且 `ON DELETE CASCADE` 不生效。

3. **`DEMO_MODE` 默认 `false`**
   演示现场离线兜底时显式开启：`DEMO_MODE=true uvicorn app.main:app --workers 1`。
   开启后前端顶栏会显示「演示模式（模拟数据）」角标。

---

## 目录

```
contract-guard/
├── 项目开发文档.md        # 规格文档 v1.1（唯一契约）
├── backend/
│   ├── app/
│   │   ├── api/v1/       # 路由：只做校验与编排
│   │   ├── core/         # 配置、常量、日志、异常
│   │   ├── models/       # SQLAlchemy ORM
│   │   ├── schemas/      # Pydantic（与 ORM 严格分离）
│   │   └── services/     # 业务逻辑（parsing / rag / agent）
│   └── tests/
└── frontend/
    └── src/
        ├── api/          # http.ts（普通接口）+ review.ts（SSE）
        ├── components/   # 左栏渲染、结论卡片、步骤条
        ├── stores/       # Pinia
        └── views/        # HomeView / ReviewView
```

---

## 常见问题

**Q：pip 安装报 `Could not find a version that satisfies`？**
A：pypi.org 与清华源在部分网络下不可达。用阿里云源：
`pip install -i https://mirrors.aliyun.com/pypi/simple -r requirements.txt`

**Q：健康检查 `llm: false`？**
A：`.env` 里 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` 未填全。健康检查只校验配置，不发起真实调用。

**Q：为什么不用 Chroma / LangChain？**
A：语料规模只有数千条法条，numpy 一批矩阵乘足够；重框架会带来同步客户端阻塞 async 事件循环、安装成功率低等问题。见文档第 20 节取舍表。
