# Use an official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Set environment variables to prevent Python from writing pyc files to disc
# and buffering stdout and stderr.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the package and dependencies
# We use -e . to install the package in editable mode or just . for regular install.
# Since we are copying the source, normal install is fine.
RUN pip install --no-cache-dir .

# Create and set the working directory for runtime to /code
# This ensures that files written to relative paths (like report.json)
# end up in the mounted volume.
WORKDIR /code

# Set the entrypoint to the CLI command
ENTRYPOINT ["ai-act-check"]

# Default command arguments (optional, can be overridden)
CMD ["--help"]
