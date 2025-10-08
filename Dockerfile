# Capital.com MCP Server - Production Docker Image
# Uses Python 3.11 slim base with non-root user for security

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user (uid 1000) for security
RUN groupadd -g 1000 mcpuser && \
    useradd -r -u 1000 -g mcpuser mcpuser && \
    chown -R mcpuser:mcpuser /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY capital_server.py .

# Switch to non-root user
USER mcpuser

# Set environment variables for logging
ENV PYTHONUNBUFFERED=1

# Run the MCP server
CMD ["python", "capital_server.py"]



