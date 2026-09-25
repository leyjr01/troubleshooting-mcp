# Supply an approved immutable Python image (including @sha256 digest).
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS build
ARG PYTHON_IMAGE
RUN echo "$PYTHON_IMAGE" | grep -Eq '@sha256:[0-9a-f]{64}$'
ENV SOURCE_DATE_EPOCH=315532800
WORKDIR /build
COPY pyproject.toml requirements.lock README.md ./
COPY deploy/runtime-linux.constraints ./
COPY src ./src
RUN python -m pip install --no-cache-dir setuptools==75.8.0 wheel==0.45.1 \
    && python -m pip wheel --no-cache-dir --no-build-isolation --only-binary=:all: \
       --wheel-dir /wheels --constraint requirements.lock --constraint runtime-linux.constraints .

FROM ${PYTHON_IMAGE}
ARG RELEASE_VERSION
ARG VCS_REF=unknown
ARG SOURCE_URL=unknown
LABEL org.opencontainers.image.title="API Gateway Troubleshooting MCP" \
      org.opencontainers.image.version="${RELEASE_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${SOURCE_URL}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp TMPDIR=/tmp
WORKDIR /app
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels api-gateway-troubleshooting-mcp \
    && python -c "import os; from importlib.metadata import version; assert version('api-gateway-troubleshooting-mcp') == os.environ['RELEASE_VERSION']" \
    && rm -rf /wheels
USER 10001:0
EXPOSE 8000
ENTRYPOINT ["python", "-m", "agt_mcp", "serve"]
CMD ["--file", "/etc/agt/config.yaml", "--transport", "http"]
