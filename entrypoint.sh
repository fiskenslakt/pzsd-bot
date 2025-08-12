#!/bin/sh

# Exit immediately if any command in this script exits with non-zero status
set -e

## Run databa
echo "Running db migrations..."
python -m alembic upgrade head

# Execute the command passed to the entrypoint (the CMD from the Dockerfile)
echo "Starting..."
exec "$@"
