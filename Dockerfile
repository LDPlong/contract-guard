# 多阶段构建：前端产物打进镜像，运行期只有一个 uvicorn 进程（单端口）。
#
# 注意：本机没有 Docker 环境，这个镜像未经实际构建验证。
# 首次在服务器上部署时，优先按 docs/部署.md 的裸机步骤走，该路径已实测。

# ---------- 1. 构建前端 ----------
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. 运行后端 ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=prod

WORKDIR /srv/backend

COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

COPY backend/ ./
# 前端产物落到 /srv/frontend/dist，与 app/main.py 里的 FRONTEND_DIST 对齐
COPY --from=web /web/dist /srv/frontend/dist

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# workers 必须为 1：解析任务、SSE 状态、BM25 索引都在进程内
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
