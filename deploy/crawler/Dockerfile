# Casefold crawler: trace any wallet on demand. Runs next to Neo4j, behind the server's reverse proxy (HTTPS).
FROM python:3.12-slim
WORKDIR /app
COPY deploy/crawler/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 crawler && mkdir -p /data && chown crawler /data
COPY casefold/ casefold/
COPY data/crypto/ data/crypto/
COPY schema/ schema/
USER crawler
ENV CRAWLER_DB=/data/crawler.sqlite
VOLUME /data
EXPOSE 8090
CMD ["uvicorn", "--factory", "casefold.crawler.api:make_app", "--host", "0.0.0.0", "--port", "8090"]
