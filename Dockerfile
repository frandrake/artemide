# ---- Stage 1: build the Astro UI ----
FROM node:20-slim AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --all-extras --no-install-project
COPY . .
# Replace whatever was in web/ during COPY with the freshly built dist.
COPY --from=web-builder /web/dist /app/web/dist
RUN uv sync --all-extras
CMD ["uv", "run", "python", "-m", "src.app"]
