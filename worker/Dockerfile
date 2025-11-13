# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We use kafka-python-ng as a pure-python client
RUN pip install --no-cache-dir kafka-python-ng psycopg2-binary

# Copy the local code to the container
COPY ./worker.py /app/worker.py

# The command to run the worker is specified in docker-compose.yml
