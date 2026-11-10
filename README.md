# ContractGuard · 合同风险审查官

上传一份合同，逐条标出高风险条款，给出法条依据与可谈的修改方向。

> **本工具仅提供风险提示与修改方向，不构成法律意见，不替代执业律师。**

面向个人（租房青年、实习生、应届生）的合同风险提示工具，只覆盖三类合同：  
房屋租赁、实习/劳动合同、培训贷/预付卡。

> 参赛作品：2026 第九届传智杯全国大学生数智创新与 AI 应用大赛 · AI WEB 网页开发挑战赛 · 本科 B 组

---

## 团队

| 代号    | 角色      | 负责范围                                      |
| ----- | ------- | ----------------------------------------- |
| A（队长） | 架构与全栈开发 | 系统架构、前端全部页面与交互、Agent 工作流与 RAG、后端 API、部署运维 |
| B     | 数据与质量   | 法规语料整理与版本核对、审查清单种子数据、合同样本脱敏、评测集标注         |
| C     | 产品与交付   | 需求调研、信息架构与视觉稿、技术文档、演示视频、提交材料              |

详细的职责边界、目录 ownership、提交规范与 9 天排期见 [`docs/团队分工.md`](docs/团队分工.md)。

---

## 当前进度

| 里程碑 | 内容                      | 状态    |
| --- | ----------------------- | ----- |
| M0  | 工程骨架、健康检查、前端首页          | ✅ 完成  |
| M1  | PDF 解析 + 条款切分 + bbox 定位 | ✅ 完成  |
| M2  | pdf.js 双栏审查台            | ✅ 完成  |
| M3  | 法规语料入库 + 检索             | ✅ 完成（五部法，1825 条） |
| M4  | Agent 工作流 + SSE         | ✅ 完成  |
| M5  | 高亮联动                    | ✅ 完成  |
| M6  | 安全分 + 报告导出              | ✅ 完成  |
| M7  | 脱敏 / 限流 / 兜底            | ✅ 完成  |
| M8  | 交付材料                    | 🟡 技术文档完成，演示视频与评测集待补 |

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
├── docs/                     # 技术文档、部署说明、演示脚本、团队分工
├── Dockerfile                # 单镜像：前端构建 + 后端运行（未在本机验证）
├── backend/
│   ├── app/
│   │   ├── api/v1/           # 路由：只做校验与编排
│   │   ├── core/             # 配置、常量、日志、异常
│   │   ├── data/             # 审查清单（3 类 24 项）+ 法规语料（5 部 1825 条）
│   │   ├── models/           # SQLAlchemy ORM
│   │   ├── schemas/          # Pydantic（与 ORM 严格分离）
│   │   └── services/         # 业务逻辑：parsing / rag / agent / llm
│   ├── scripts/              # 建索引、抓语料、端到端冒烟
│   └── tests/                # 84 项
└── frontend/
    └── src/
        ├── api/              # http.ts（普通接口）+ review.ts（SSE）
        ├── components/       # 条款视图、结论卡片、步骤条、打印报告
        ├── stores/           # Pinia
        └── views/            # Home / Review / Guide / LawLibrary
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
