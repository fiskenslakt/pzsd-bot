FROM python:3.12-slim-bookworm
# Astral magic to make UV play nicely
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Install dependencies
WORKDIR /app
RUN uv sync --locked --no-dev

# Add venv CLI executables to PATH so alembic can run
ENV PATH="/app/.venv/bin:$PATH"

# Copy and set permissions for the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint script to run on container start
ENTRYPOINT ["entrypoint.sh"]

# Set the default command to run the bot
CMD ["python", "-m", "pzsd_bot"]
