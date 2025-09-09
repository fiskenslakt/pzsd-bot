FROM python:3.12-slim-bookworm

# Install some extra packages I want
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client \
        less \
        procps \
        htop && \
    rm -rf /var/lib/apt/lists/*

# Astral magic to make UV play nicely
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Install dependencies
WORKDIR /app
RUN uv sync --no-dev

# Add venv CLI executables to PATH so alembic can run
ENV PATH="/app/.venv/bin:$PATH"

# Copy and set permissions for the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint script to run on container start
ENTRYPOINT ["entrypoint.sh"]

# Run the bot (sent to entrypoint)
CMD ["python", "-m", "pzsd_bot"]

# This tells GitHub that the fiskenslakt/pzsd-bot code repo is allowed to push to the ghcr.io/fiskenslakt/pzsd-bot container repository
# which will be useful when we set up CI/CD
LABEL org.opencontainers.image.source=https://github.com/fiskenslakt/pzsd-bot/
