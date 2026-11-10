#!/bin/sh
# 容器入口：法规索引不存在就先建一次。
# 语料随镜像发布，但数据目录常被挂载成卷，所以不能在构建期把索引写死进去。
set -e

INDEX_FILE="${INDEX_DIR:-./data/index}/bm25.pkl"

if [ ! -f "$INDEX_FILE" ]; then
    echo "[entrypoint] 法规索引缺失，开始构建：$INDEX_FILE"
    python -m scripts.build_index
fi

exec "$@"
