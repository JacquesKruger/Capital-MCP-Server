#!/bin/bash
# Capital.com MCP Server - One-Click Installer
# This script sets up everything you need to get started

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Capital.com MCP Server - Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "✅ Docker found"
    USE_DOCKER=true
else
    echo "⚠️  Docker not found - will use local Python installation"
    USE_DOCKER=false
fi

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✅ Python $PYTHON_VERSION found"
else
    echo "❌ Python 3 not found. Please install Python 3.11 or later."
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1: Setting up credentials directory"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Create credentials file if it doesn't exist
if [ ! -f secrets/.env.demo ]; then
    cat > secrets/.env.demo << 'EOF'
# Capital.com Demo API Credentials
# Get these from: https://capital.com → Settings → API Access

CAP_ENVIRONMENT=demo
CAP_API_KEY=your_demo_api_key_here
CAP_IDENTIFIER=your_demo_identifier_here
CAP_PASSWORD=your_demo_password_here
EOF
    chmod 600 secrets/.env.demo
    echo "✅ Created secrets/.env.demo"
    echo ""
    echo "⚠️  IMPORTANT: You need to add your Capital.com credentials!"
    echo "   Edit: secrets/.env.demo"
    echo "   Get credentials at: https://capital.com"
    NEED_CREDENTIALS=true
else
    echo "✅ Credentials file already exists"
    NEED_CREDENTIALS=false
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2: Installing dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$USE_DOCKER" = true ]; then
    echo "Building Docker image..."
    docker build -q -t capital-mcp-server . && echo "✅ Docker image built successfully" || {
        echo "❌ Docker build failed"
        exit 1
    }
else
    echo "Setting up Python virtual environment..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✅ Virtual environment created"
    fi
    
    echo "Installing Python packages..."
    source venv/bin/activate
    pip install -q -r requirements.txt && echo "✅ Python packages installed" || {
        echo "❌ Python package installation failed"
        exit 1
    }
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3: Testing server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$USE_DOCKER" = true ]; then
    echo "Testing Docker server..."
    TEST_OUTPUT=$(echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | \
        docker run --rm -i --env-file secrets/.env.demo capital-mcp-server 2>/dev/null | grep -o '"name":"Capital.com Trading"' || echo "")
    
    if [ -n "$TEST_OUTPUT" ]; then
        echo "✅ Server test successful"
    else
        echo "⚠️  Server test returned unexpected output (this may be okay if credentials aren't set)"
    fi
else
    echo "Testing Python server..."
    source venv/bin/activate
    TEST_OUTPUT=$(echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | \
        python capital_server.py 2>/dev/null | grep -o '"name":"Capital.com Trading"' || echo "")
    
    if [ -n "$TEST_OUTPUT" ]; then
        echo "✅ Server test successful"
    else
        echo "⚠️  Server test returned unexpected output (this may be okay if credentials aren't set)"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Installation Complete! 🎉"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$NEED_CREDENTIALS" = true ]; then
    echo "⚠️  NEXT STEP: Add your Capital.com credentials"
    echo ""
    echo "   1. Edit the file: secrets/.env.demo"
    echo "   2. Replace the placeholder values with your actual credentials"
    echo "   3. Get credentials from: https://capital.com → Settings → API"
    echo ""
    echo "   Quick edit command:"
    echo "   $ nano secrets/.env.demo"
    echo ""
fi

echo "📖 Configuration for your MCP client:"
echo ""

if [ "$USE_DOCKER" = true ]; then
    echo "   For Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):"
    echo ""
    echo '   {'
    echo '     "mcpServers": {'
    echo '       "capital-trading": {'
    echo '         "command": "docker",'
    echo '         "args": ["run", "--rm", "-i", "--env-file", "'"$SCRIPT_DIR"'/secrets/.env.demo", "capital-mcp-server"]'
    echo '       }'
    echo '     }'
    echo '   }'
else
    echo "   For Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):"
    echo ""
    echo '   {'
    echo '     "mcpServers": {'
    echo '       "capital-trading": {'
    echo '         "command": "'"$SCRIPT_DIR"'/venv/bin/python",'
    echo '         "args": ["'"$SCRIPT_DIR"'/capital_server.py"],'
    echo '         "env": {'
    echo '           "CAP_ENVIRONMENT": "demo",'
    echo '           "CAP_API_KEY": "your_demo_api_key",'
    echo '           "CAP_IDENTIFIER": "your_demo_identifier",'
    echo '           "CAP_PASSWORD": "your_demo_password"'
    echo '         }'
    echo '       }'
    echo '     }'
    echo '   }'
fi

echo ""
echo "   For Cursor (~/.cursor/mcp.json):"
echo ""
echo '   {'
echo '     "mcpServers": {'
echo '       "capital-trading": {'
echo '         "command": "/bin/bash",'
echo '         "args": ["'"$SCRIPT_DIR"'/run-mcp-server.sh"],'
echo '         "env": {"CAP_ENVIRONMENT": "demo"}'
echo '       }'
echo '     }'
echo '   }'
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Quick Start Commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Add credentials:"
echo "  $ nano secrets/.env.demo"
echo ""
echo "  Test server:"
if [ "$USE_DOCKER" = true ]; then
    echo "  $ ./test_mcp.sh"
else
    echo "  $ source venv/bin/activate && python test_server.py"
fi
echo ""
echo "  Read documentation:"
echo "  $ cat readme.txt"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Happy Trading! 🚀 (Remember: Start with demo mode!)"
echo ""

