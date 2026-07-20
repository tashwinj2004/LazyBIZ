# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's layer caching
COPY backend/requirements.txt /app/backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application source directories
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Create the data directory for uploads, user storage, and DB persistence
RUN mkdir -p /app/data

# Expose port 5001 (which is the default port the backend runs on)
EXPOSE 5001

# Change working directory to backend so direct imports (like 'import mcp_tools') resolve correctly
WORKDIR /app/backend

# Run the FastAPI app via Uvicorn, binding to 0.0.0.0 so it is accessible outside the container
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5001"]
