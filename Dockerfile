FROM python:3.12-slim
RUN pip install uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --all-extras --no-install-project
COPY . .
RUN uv sync --all-extras
CMD ["uv", "run", "python", "-m", "src.app"]
