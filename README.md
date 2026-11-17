# ContractGuard · 合同风险审查官

上传一份合同，逐条标出高风险条款，给出法条依据与可谈的修改方向。

> **本工具仅提供风险提示与修改方向，不构成法律意见，不替代执业律师。**

面向个人（租房青年、实习生、应届生）的合同风险提示工具，只覆盖三类合同：  
房屋租赁、实习/劳动合同、培训贷/预付卡。

页面右下角还有一个答疑助手：解释法条与名词、说明某类条款为什么有风险，每条回答附法条依据；
预测输赢、代写条款、代理案件的提问一律拒答。

> 参赛作品：2026 第九届传智杯全国大学生数智创新与 AI 应用大赛 · AI WEB 网页开发挑战赛 · 本科 B 组
>
> **在线演示**：http://118.31.60.214:8000（无需登录，匿名即用）

---

## 项目介绍

### 解决什么问题

即将签约的普通人没有能力逐条识别"押金一律不退""违约金两个月租金""放弃社保"这类陷阱条款，
也不具备把《民法典》具体条号与合同条款对应起来的法律检索能力。ContractGuard 在 10~30 秒内完成：
合同类型识别 → 条款自动切分 → 逐条风险核对 → 结论与原文双视图对照 → 一页可导出的审查报告。

### 核心功能

- **逐条流式审查**：24 项审查清单（租赁 8 / 劳动 8 / 预付卡 8），命中即实时上屏，置信度不足标"待复核"
- **法条依据到条号**：本地法规库收录《民法典》《民事诉讼法》《消费者权益保护法》《劳动合同法》《社会保险法》全文（1825 个检索块），每条结论附条号与原文，防幻觉四层闸门保证引用真实存在
- **结论与原文双视图联动**：条款视图与原版 PDF 可切换，命中条款带彩色风险边，点击结论直接跳转
- **谈判次序**：结论标注"必守 / 可谈 / 可让步"，一页速览先谈什么、后让什么
- **多模态拍照合同**：手机拍的照片直接审查（视觉模型直读）
- **答疑助手**：就当前合同追问细节，回答先给检索到的法条依据；越界问题一律拒答
- **报告导出**：一页速览报告可打印导出 PDF
- **空白模板识别**：官方示范文本自动降级为"待填"提示，不把"还没填"当"没约定"

### 当前进度

| 里程碑 | 内容                      | 状态    |
| --- | ----------------------- | ----- |
| M0  | 工程骨架、健康检查、前端首页          | ✅ 完成  |
| M1  | PDF 解析 + 条款切分 + bbox 定位 | ✅ 完成  |
| M2  | pdf.js 双栏审查台            | ✅ 完成  |
| M3  | 法规语料入库 + 检索             | ✅ 完成（五部法，1825 条） |
| M4  | Agent 工作流 + SSE         | ✅ 完成  |
| M5  | 高亮联动                    | ✅ 完成  |
| M6  | 安全分 + 报告导出              | ✅ 完成  |
| M7  | 脱敏 / 限流 / 兜底            | ✅ 完成（限流为进程内滑动窗口） |
| M8  | 交付材料                    | 🟡 技术文档 / 评测集 / 作品介绍完成，演示视频待录 |

规格文档：[`docs/项目开发文档.md`](docs/项目开发文档.md)（v1.2，实现以此为准）；
评测结果：[`docs/评测结果.md`](docs/评测结果.md)（9 份样本 35/35 召回，示范文本误报 1/83）。

---

## 技术架构

```
┌─ 前端 Vue3 + TS + Pinia + pdf.js ────────────────────────────┐
│  首页上传 / 双栏审查台（条款 ⇆ 原版 PDF）/ 法规库 / 答疑抽屉      │
└──────────────┬───────────────────────────────────────────────┘
               │ POST SSE 流式（fetch + ReadableStream）
┌──────────────▼───────────────────────────────────────────────┐
│ 后端 FastAPI（单进程单端口，托管前端构建产物）                    │
│  ├─ 限流 / 每日配额 / 请求上下文（core/）                        │
│  ├─ API 层：上传解析 · SSE 审查 · 答疑 · 法规库 · 健康检查        │
│  ├─ services/parsing：PyMuPDF 解析 → 条款切分 → 类型识别        │
│  ├─ services/rag：BM25(jieba) ⇄ 向量(bge-m3) → RRF 融合检索     │
│  ├─ services/agent：审查清单 → 预筛 → 逐条判定 → 防幻觉闸门 → 汇总 │
│  ├─ services/llm：OpenAI 兼容客户端（重试 / 并发 / 超时）          │
│  └─ SQLite（WAL）+ 法条索引文件（BM25 pickle + meta）            │
└──────────────────────────────────────────────────────────────┘
```

**技术栈**：Vue 3 + TypeScript + Vite + Tailwind CSS + Pinia + pdf.js；
Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / PyMuPDF / rank_bm25 + jieba；
大模型走 OpenAI 兼容协议，由 `services/llm/client.py` 统一调用。

**关键设计决策**：

- **条款预筛**：关键词 + 文档内 BM25 把每个审查项收敛到 Top-K 候选，模型调用量降一个量级
- **防幻觉四层闸门**：JSON 校验 → 引用存在性 → 越界丢弃 → 零命中降级"待复核"，法条事实完全由本地库供给
- **混合检索自动降级**：未配置 embedding 服务时自动降级纯 BM25，任何部署形态检索都可用
- **单进程单端口**：后端直接托管前端构建产物，`/api/v1/*` 走接口、其余回落 `index.html`，部署无需 nginx
- **面向公网的防护**：限流（重操作 12 次/分钟）+ 每日配额（审查 1000 次/天）+ 平台额度三层防刷，上传魔数/大小双校验

---

## 安装运行指南

### 环境要求

- Python 3.11+（推荐 3.12）、Node.js 18+
- 一个 OpenAI 兼容的模型服务（Base URL + API Key + 模型名）

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

### 3. 验证与索引

```bash
curl http://127.0.0.1:8000/api/v1/health
```

```json
{"status":"ok","db":true,"vector":false,"index_built":false,"llm":true,"demo_mode":false}
```

`index_built=false` 时先建法规索引（五部法，1825 条）：

```bash
cd backend && python -m scripts.build_index
```

### 4. 单进程部署（演示服务器）

构建一次前端，产物就由后端进程直接托管，部署是"一个进程、一个端口"，不用 nginx 反代：

```bash
cd frontend && npm run build && cd ..       # 产出 frontend/dist
cd backend && python -m scripts.build_index  # 首次：建法规索引
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
# 浏览器打开 http://<服务器IP>:8000
```

`/api/v1/*` 走接口，其余路径回落到 `index.html`（SPA 路由）；接口写错仍返回 JSON 404，不会被 HTML 吞掉。
服务器上的完整步骤（systemd、nginx 反代与 SSE 缓冲、Docker、演示前检查）见 [`docs/部署.md`](docs/部署.md)。

### 5. 运行时约束（违反会导致状态错乱）

1. **uvicorn 必须 `--workers 1`**
   解析任务、SSE 连接状态、BM25 内存索引都驻留在单进程内，多 worker 会导致任务丢失与索引不一致。
2. **SQLite 自动开 WAL + 外键**
   代码在连接时执行 `PRAGMA journal_mode=WAL; foreign_keys=ON`，否则 SSE 长连接期间写 findings 会 `database is locked`，且 `ON DELETE CASCADE` 不生效。
3. **`DEMO_MODE` 默认 `false`**
   演示现场离线兜底时显式开启：`DEMO_MODE=true uvicorn app.main:app --workers 1`。
   开启后前端顶栏会显示「演示模式（模拟数据）」角标。
4. **环境变量**：全部配置项与说明见根目录 [`.env.example`](.env.example)（应用 / 数据库 / 存储 / 模型服务 / 检索 / 限流与配额）。

---

## 团队信息

| 代号    | 角色      | 负责范围                                      |
| ----- | ------- | ----------------------------------------- |
| A（队长） | 架构与全栈开发 | 系统架构、前端全部页面与交互、Agent 工作流与 RAG、后端 API、部署运维 |
| B     | 数据与质量   | 法规语料整理与版本核对、审查清单种子数据、合同样本脱敏、评测集标注         |
| C     | 产品与交付   | 需求调研、信息架构与视觉稿、技术文档、演示视频、提交材料              |

**协作方式**：跨目录修改先沟通，禁止直接 push 他人负责的目录；提交信息遵循
`<type>(<scope>): <中文描述>`（feat / fix / docs / test / chore），main 分支保持随时可演示的可运行状态。

---

## 目录

```
contract-guard/
├── docs/                     # 技术文档、开发规格、部署说明、评测结果、作品介绍
├── Dockerfile                # 单镜像：前端构建 + 后端运行（未在本机验证）
├── backend/
│   ├── app/
│   │   ├── api/v1/           # 路由：只做校验与编排
│   │   ├── core/             # 配置、常量、日志、异常、限流
│   │   ├── data/             # 审查清单（3 类 24 项）+ 法规语料（5 部 1825 条）
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic（与 ORM 严格分离）
│   │   └── services/         # 业务逻辑：parsing / rag / agent / llm / assistant
│   ├── scripts/              # 建索引、抓语料、冒烟、评测集跑分
│   └── tests/                # 124 项（含 9 份评测样本）
└── frontend/
    └── src/
        ├── api/              # http.ts（普通接口）+ review.ts（SSE）
        ├── lib/              # SSE 帧解析、错误上报、公共配置
        ├── components/       # 条款视图、结论卡片、步骤条、打印报告
        ├── stores/           # Pinia
        └── views/            # Home / Review / Guide / LawLibrary / Privacy / Terms / Feedback
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
