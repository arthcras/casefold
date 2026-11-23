# Casefold back office (office.casefoldcrypto.com): the workspace, the app with "Trace this wallet now", and the
# crawler with the server's token. Behind Cloudflare Access; nginx also checks the Access token itself (fail closed).
FROM nginx:1.27-alpine
COPY deploy/office/default.conf.template /etc/nginx/templates/default.conf.template
COPY web/workspace.html web/crypto.html /usr/share/nginx/html/
COPY web/data/crypto.json web/data/sanctions_names.json web/data/txindex.json /usr/share/nginx/html/data/
COPY web/vendor/relate/ /usr/share/nginx/html/vendor/relate/
RUN echo "ok" > /usr/share/nginx/html/healthz
ENV NGINX_ENVSUBST_FILTER=CRAWLER_TOKEN
EXPOSE 80
