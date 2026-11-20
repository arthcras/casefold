# Casefold Crypto Intelligence: the public website and app, served by nginx. Only the public pages go in:
# the back office (workspace.html), the platform console and other internal pages are left out on purpose.
FROM nginx:1.27-alpine
COPY deploy/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/site.html web/crypto.html /usr/share/nginx/html/
COPY web/data/crypto.json web/data/sanctions_names.json web/data/txindex.json /usr/share/nginx/html/data/
COPY web/vendor/relate/ /usr/share/nginx/html/vendor/relate/
RUN echo "ok" > /usr/share/nginx/html/healthz
EXPOSE 80
