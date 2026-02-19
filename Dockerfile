FROM python:3.11.14-bookworm

WORKDIR /app

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
COPY . /app/

RUN chmod +x start.sh

ENV UIPATH_DEV_SERVER_PORT=80
ENV UIPATH_DEV_SERVER_HOST=0.0.0.0

CMD ["/bin/sh", "/app/start.sh"]
