# PIP 生产镜像：单阶段，纯标准库，无第三方依赖
FROM python:3.12-slim

LABEL org.opencontainers.image.title="PIP 情报日报" \
      org.opencontainers.image.description="31 源采集 + 全球覆盖扫描 + 赛博情报中心" \
      org.opencontainers.image.source="https://github.com/xqd-app/Information-Retrieval-Technology"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_HOST=0.0.0.0 \
    PIP_PORT=8080 \
    PIP_LOG_LEVEL=INFO

WORKDIR /app

# 先只拷代码，利用层缓存（无依赖安装，秒级构建）
COPY pip_app/ /app/pip_app/
COPY pip_skeleton/ /app/pip_skeleton/
COPY packetvoyage-master/ /app/packetvoyage-master/

# 构建产物若已存在则直接用；不存在时容器启动会尝试生成
COPY pip_app/web/index.html* /app/pip_app/web/ 2>/dev/null || true

RUN mkdir -p /app/pip_app/data/items \
    && python -c "import sys; sys.path.insert(0, '/app'); from pip_app import server; print('import ok')"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

CMD ["python", "-m", "pip_app.server"]
