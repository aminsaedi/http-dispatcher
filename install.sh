#!/bin/bash
set -e

# HTTP Dispatcher Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | bash -s -- [coordinator|agent] [options]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
MODE=""
COORDINATOR_URL=""
AGENT_ID=""
INSTALL_DIR="/opt/http-dispatcher"
SERVICE_USER="http-dispatcher"
COORDINATOR_HOST="0.0.0.0"
COORDINATOR_PORT="8000"
TAILSCALE_HOSTNAME=""
TAILSCALE_IP=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        coordinator|agent)
            MODE="$1"
            shift
            ;;
        --coordinator-url)
            COORDINATOR_URL="$2"
            shift 2
            ;;
        --agent-id)
            AGENT_ID="$2"
            shift 2
            ;;
        --host)
            COORDINATOR_HOST="$2"
            shift 2
            ;;
        --port)
            COORDINATOR_PORT="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --help)
            echo "HTTP Dispatcher Installation Script"
            echo ""
            echo "Usage:"
            echo "  curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | bash -s -- coordinator"
            echo "  curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | bash -s -- agent [--coordinator-url URL]"
            echo ""
            echo "Options:"
            echo "  coordinator              Install as coordinator"
            echo "  agent                    Install as agent (auto-detects coordinator if Tailscale is used)"
            echo "  --coordinator-url URL    Coordinator URL (optional if Tailscale auto-detection works)"
            echo "  --agent-id ID            Agent ID (optional, auto-generated if not provided)"
            echo "  --host HOST              Coordinator bind host (default: 0.0.0.0)"
            echo "  --port PORT              Coordinator bind port (default: 8000)"
            echo "  --install-dir DIR        Installation directory (default: /opt/http-dispatcher)"
            echo ""
            echo "Tailscale Integration:"
            echo "  If Tailscale is detected, the installer will:"
            echo "  - Auto-detect coordinator hostname for agents"
            echo "  - Bind coordinator to Tailscale IP"
            echo "  - Configure monitoring to use Tailscale networking"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}" 
   echo "Please run: sudo bash -c \"\$(curl -fsSL ...)\""
   exit 1
fi

# Tailscale detection functions
detect_tailscale() {
    # Check if Tailscale is installed and running
    if command -v tailscale &> /dev/null; then
        # Get Tailscale status
        if tailscale status &> /dev/null; then
            # Get Tailscale hostname
            TAILSCALE_HOSTNAME=$(tailscale status --json 2>/dev/null | grep -o '"Name":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
            
            # Get Tailscale IP (100.x.x.x)
            TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1 || echo "")
            
            if [[ -n "$TAILSCALE_HOSTNAME" ]] || [[ -n "$TAILSCALE_IP" ]]; then
                return 0
            fi
        fi
    fi
    return 1
}

# Determine mode if not specified
if [[ -z "$MODE" ]]; then
    echo -e "${YELLOW}Mode not specified. Please specify 'coordinator' or 'agent'${NC}"
    echo "Usage: curl ... | bash -s -- coordinator"
    exit 1
fi

# Detect Tailscale
if detect_tailscale; then
    echo -e "${GREEN}✓ Tailscale detected${NC}"
    if [[ -n "$TAILSCALE_HOSTNAME" ]]; then
        echo -e "${BLUE}  Hostname: ${TAILSCALE_HOSTNAME}${NC}"
    fi
    if [[ -n "$TAILSCALE_IP" ]]; then
        echo -e "${BLUE}  IP: ${TAILSCALE_IP}${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Tailscale not detected - using standard networking${NC}"
fi

# Auto-detect coordinator URL for agents if not provided
if [[ "$MODE" == "agent" ]]; then
    if [[ -z "$COORDINATOR_URL" ]]; then
        # Try to auto-detect coordinator
        if detect_tailscale && [[ -n "$TAILSCALE_HOSTNAME" ]]; then
            # Try common coordinator hostnames
            COORDINATOR_CANDIDATES=("coordinator" "http-dispatcher-coordinator" "dispatcher-coordinator" "server" "dispatcher")
            
            # First, try to find by hostname pattern
            for candidate in "${COORDINATOR_CANDIDATES[@]}"; do
                if tailscale status 2>/dev/null | grep -q "$candidate"; then
                    COORDINATOR_URL="http://${candidate}:8000"
                    echo -e "${GREEN}✓ Auto-detected coordinator: ${COORDINATOR_URL}${NC}"
                    break
                fi
            done
            
            # If not found, show available hosts and let user pick
            if [[ -z "$COORDINATOR_URL" ]]; then
                echo -e "${YELLOW}Available Tailscale hosts:${NC}"
                tailscale status 2>/dev/null | grep -E "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | while read -r line; do
                    hostname=$(echo "$line" | awk '{print $2}')
                    ip=$(echo "$line" | awk '{print $1}')
                    echo "  - $hostname ($ip)"
                done
                echo ""
                echo -e "${YELLOW}Tip: Use --coordinator-url http://hostname:8000 to specify coordinator${NC}"
            fi
            
            # If still not found, prompt user
            if [[ -z "$COORDINATOR_URL" ]]; then
                echo -e "${YELLOW}Could not auto-detect coordinator.${NC}"
                echo -e "${YELLOW}Available Tailscale hosts:${NC}"
                tailscale status 2>/dev/null | grep -E "^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | head -5 || echo "  (none found)"
                echo ""
                echo -e "${RED}Error: --coordinator-url is required for agent mode${NC}"
                echo "Example: --coordinator-url http://coordinator-hostname:8000"
                exit 1
            fi
        else
            echo -e "${RED}Error: --coordinator-url is required for agent mode${NC}"
            echo "Example: --coordinator-url http://coordinator-ip:8000"
            exit 1
        fi
    fi
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}HTTP Dispatcher Installation${NC}"
echo -e "${BLUE}Mode: ${MODE}${NC}"
if [[ "$MODE" == "coordinator" ]] && detect_tailscale && [[ -n "$TAILSCALE_HOSTNAME" ]]; then
    echo -e "${BLUE}Tailscale: ${TAILSCALE_HOSTNAME}${NC}"
fi
if [[ "$MODE" == "agent" ]] && [[ -n "$COORDINATOR_URL" ]]; then
    echo -e "${BLUE}Coordinator: ${COORDINATOR_URL}${NC}"
fi
echo -e "${BLUE}========================================${NC}"

# Detect installation method
# If running from curl, we need to download the files
# For now, assume we're in the project directory
if [[ -f "main.py" ]] && [[ -d "src" ]]; then
    echo -e "${GREEN}Detected local installation from source${NC}"
    SOURCE_DIR="$(pwd)"
else
    echo -e "${RED}Error: Installation files not found in current directory${NC}"
    echo "Please run this script from the http-dispatcher project directory"
    echo "Or use: curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | bash -s -- [mode]"
    exit 1
fi

# Create installation directory
echo -e "${BLUE}Creating installation directory: ${INSTALL_DIR}${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"/{bin,etc,lib,monitoring}

# Copy application files
echo -e "${BLUE}Copying application files...${NC}"
cp -r "$SOURCE_DIR"/src "$INSTALL_DIR"/lib/
cp "$SOURCE_DIR"/main.py "$INSTALL_DIR"/bin/
cp "$SOURCE_DIR"/requirements.txt "$INSTALL_DIR"/

# Copy monitoring files if coordinator
if [[ "$MODE" == "coordinator" ]]; then
    if [[ -d "$SOURCE_DIR/monitoring" ]]; then
        cp -r "$SOURCE_DIR"/monitoring "$INSTALL_DIR"/
    fi
    if [[ -f "$SOURCE_DIR/docker-compose.monitoring.yml" ]]; then
        cp "$SOURCE_DIR"/docker-compose.monitoring.yml "$INSTALL_DIR"/monitoring/
    fi
    
    # Update Prometheus config with Tailscale IP if available
    if detect_tailscale && [[ -n "$TAILSCALE_IP" ]]; then
        echo -e "${BLUE}Updating Prometheus config with Tailscale IP: ${TAILSCALE_IP}${NC}"
        sed -i.bak "s|host.docker.internal:8000|${TAILSCALE_IP}:${COORDINATOR_PORT}|g" "$INSTALL_DIR/monitoring/prometheus.yml"
        rm -f "$INSTALL_DIR/monitoring/prometheus.yml.bak"
    elif detect_tailscale && [[ -n "$TAILSCALE_HOSTNAME" ]]; then
        echo -e "${BLUE}Updating Prometheus config with Tailscale hostname: ${TAILSCALE_HOSTNAME}${NC}"
        sed -i.bak "s|host.docker.internal:8000|${TAILSCALE_HOSTNAME}:${COORDINATOR_PORT}|g" "$INSTALL_DIR/monitoring/prometheus.yml"
        rm -f "$INSTALL_DIR/monitoring/prometheus.yml.bak"
    fi
fi

# Check for Python 3
echo -e "${BLUE}Checking Python 3 installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Please install Python 3.8+ first.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Found Python ${PYTHON_VERSION}${NC}"

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r "$INSTALL_DIR"/requirements.txt --quiet

# Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo -e "${BLUE}Creating service user: ${SERVICE_USER}${NC}"
    useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
fi

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create systemd service file
echo -e "${BLUE}Creating systemd service...${NC}"
if [[ "$MODE" == "coordinator" ]]; then
    # If Tailscale is available, bind to both 0.0.0.0 and Tailscale IP
    BIND_ARGS="--host $COORDINATOR_HOST --port $COORDINATOR_PORT"
    if detect_tailscale && [[ -n "$TAILSCALE_IP" ]]; then
        echo -e "${GREEN}✓ Binding coordinator to Tailscale IP: ${TAILSCALE_IP}${NC}"
        BIND_ARGS="$BIND_ARGS --bind ${TAILSCALE_IP}:${COORDINATOR_PORT}"
    fi
    
    cat > /etc/systemd/system/http-dispatcher-coordinator.service <<EOF
[Unit]
Description=HTTP Dispatcher Coordinator
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/python3 $INSTALL_DIR/bin/main.py --mode coordinator $BIND_ARGS
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    SERVICE_NAME="http-dispatcher-coordinator"
else
    # Generate agent ID if not provided
    if [[ -z "$AGENT_ID" ]]; then
        AGENT_ID="agent-$(hostname)-$(date +%s)"
    fi
    
    cat > /etc/systemd/system/http-dispatcher-agent.service <<EOF
[Unit]
Description=HTTP Dispatcher Agent
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="DISPATCHER_COORDINATOR_URL=$COORDINATOR_URL"
Environment="DISPATCHER_AGENT_ID=$AGENT_ID"
ExecStart=/usr/bin/python3 $INSTALL_DIR/bin/main.py --mode agent --coordinator-url $COORDINATOR_URL --agent-id $AGENT_ID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    SERVICE_NAME="http-dispatcher-agent"
fi

# Create monitoring service for coordinator
if [[ "$MODE" == "coordinator" ]]; then
    echo -e "${BLUE}Creating monitoring service...${NC}"
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Docker is not installed. Installing Docker...${NC}"
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
    fi
    
    # Check if docker-compose is installed
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${YELLOW}Docker Compose is not installed. Installing...${NC}"
        # Install docker-compose v2 (docker compose)
        if ! docker compose version &> /dev/null; then
            # Fallback to docker-compose v1
            curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            chmod +x /usr/local/bin/docker-compose
        fi
    fi
    
    # Use docker compose (v2) if available, otherwise docker-compose (v1)
    DOCKER_COMPOSE_CMD="docker compose"
    if ! docker compose version &> /dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
    
    cat > /etc/systemd/system/http-dispatcher-monitoring.service <<EOF
[Unit]
Description=HTTP Dispatcher Monitoring Stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR/monitoring
ExecStart=/bin/bash -c "$DOCKER_COMPOSE_CMD -f $INSTALL_DIR/monitoring/docker-compose.monitoring.yml up -d"
ExecStop=/bin/bash -c "$DOCKER_COMPOSE_CMD -f $INSTALL_DIR/monitoring/docker-compose.monitoring.yml down"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
fi

# Create management script
echo -e "${BLUE}Creating management script...${NC}"
cat > /usr/local/bin/http-dispatcher <<'SCRIPT_EOF'
#!/bin/bash
SERVICE_NAME="$1"
ACTION="$2"

if [[ -z "$SERVICE_NAME" ]] || [[ -z "$ACTION" ]]; then
    echo "Usage: http-dispatcher {coordinator|agent|monitoring} {start|stop|restart|status|logs|enable|disable}"
    exit 1
fi

case "$SERVICE_NAME" in
    coordinator)
        SERVICE="http-dispatcher-coordinator"
        ;;
    agent)
        SERVICE="http-dispatcher-agent"
        ;;
    monitoring)
        SERVICE="http-dispatcher-monitoring"
        ;;
    *)
        echo "Unknown service: $SERVICE_NAME"
        exit 1
        ;;
esac

case "$ACTION" in
    start)
        sudo systemctl start "$SERVICE"
        ;;
    stop)
        sudo systemctl stop "$SERVICE"
        ;;
    restart)
        sudo systemctl restart "$SERVICE"
        ;;
    status)
        sudo systemctl status "$SERVICE"
        ;;
    logs)
        sudo journalctl -u "$SERVICE" -f
        ;;
    enable)
        sudo systemctl enable "$SERVICE"
        ;;
    disable)
        sudo systemctl disable "$SERVICE"
        ;;
    *)
        echo "Unknown action: $ACTION"
        exit 1
        ;;
esac
SCRIPT_EOF

chmod +x /usr/local/bin/http-dispatcher

# Reload systemd
systemctl daemon-reload

# Enable and start services
echo -e "${BLUE}Enabling and starting services...${NC}"
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

if [[ "$MODE" == "coordinator" ]]; then
    systemctl enable http-dispatcher-monitoring
    systemctl start http-dispatcher-monitoring
fi

# Wait a moment for services to start
sleep 2

# Check service status
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}✓ Service $SERVICE_NAME is running${NC}"
else
    echo -e "${RED}✗ Service $SERVICE_NAME failed to start${NC}"
    echo "Check logs with: journalctl -u $SERVICE_NAME"
    exit 1
fi

if [[ "$MODE" == "coordinator" ]]; then
    if systemctl is-active --quiet http-dispatcher-monitoring; then
        echo -e "${GREEN}✓ Monitoring service is running${NC}"
    else
        echo -e "${YELLOW}⚠ Monitoring service may need a moment to start${NC}"
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Service Management:"
echo "  http-dispatcher $MODE status    - Check service status"
echo "  http-dispatcher $MODE logs       - View service logs"
echo "  http-dispatcher $MODE restart    - Restart service"
echo ""

if [[ "$MODE" == "coordinator" ]]; then
    echo "Monitoring:"
    echo "  http-dispatcher monitoring status  - Check monitoring status"
    echo "  http-dispatcher monitoring logs    - View monitoring logs"
    echo ""
    echo "Access Points:"
    if detect_tailscale && [[ -n "$TAILSCALE_HOSTNAME" ]]; then
        echo "  Coordinator API: http://$TAILSCALE_HOSTNAME:$COORDINATOR_PORT (Tailscale)"
        echo "  Metrics: http://$TAILSCALE_HOSTNAME:$COORDINATOR_PORT/metrics (Tailscale)"
        if [[ -n "$TAILSCALE_IP" ]]; then
            echo "  Coordinator API: http://$TAILSCALE_IP:$COORDINATOR_PORT (Tailscale IP)"
        fi
    else
        echo "  Coordinator API: http://$COORDINATOR_HOST:$COORDINATOR_PORT"
        echo "  Metrics: http://$COORDINATOR_HOST:$COORDINATOR_PORT/metrics"
    fi
    echo "  Grafana: http://localhost:3000 (admin/admin)"
    echo "  Prometheus: http://localhost:9090"
    echo ""
fi

if [[ "$MODE" == "agent" ]]; then
    echo "Agent Configuration:"
    echo "  Agent ID: $AGENT_ID"
    echo "  Coordinator: $COORDINATOR_URL"
    if detect_tailscale && [[ -n "$TAILSCALE_HOSTNAME" ]]; then
        echo "  Tailscale: $TAILSCALE_HOSTNAME"
    fi
    echo ""
fi

