#!/bin/bash
# Capital.com MCP Server Launcher
# This script runs the MCP server with proper path handling

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the Docker container with the env file
docker run --rm -i \
  --env-file "$SCRIPT_DIR/secrets/.env.demo" \
  capital-mcp-server



