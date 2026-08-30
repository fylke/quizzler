# Use immutable image references for supply-chain safety
FROM python:3.14-slim@sha256:83ff1d245a3d57d04152252d3ef9cb361494d0b3395abd65a5ebe91c401c8e83

# Set working directory in container
WORKDIR /app

RUN apt-get update \
	&& apt-get upgrade -y \
	&& rm -rf /var/lib/apt/lists/*

# Safer Python runtime defaults for containers
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

# Install uv from an immutable image reference
COPY --from=ghcr.io/astral-sh/uv@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install production dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Replace vulnerable packages reported in the Python base image metadata.
RUN python -m pip install --no-cache-dir "setuptools>=78.1.1" "msgpack>=1.2.1" \
	&& python -m pip uninstall -y wheel jaraco.context || true

# Create runtime directories used by bind mounts/temp files
RUN mkdir -p /app/database /tmp

# Create unprivileged runtime identity
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home --home-dir /app --shell /usr/sbin/nologin app

# Copy application code and static files
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/ ./scripts/

RUN chown -R 10001:10001 /app

USER 10001:10001

# Expose port 5000
EXPOSE 5000

# Run Flask app
CMD ["sh", "scripts/entrypoint.sh"]
