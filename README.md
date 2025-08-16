# HTTP Dispatcher

A distributed HTTP request system with IPv6 support, featuring agent-based request distribution, round-robin load balancing, and a TUI monitoring interface.

## Features

- **Agent Mode**: Outbound gateway nodes that execute HTTP requests using specific IPv6 addresses
- **Coordinator Mode**: Central server managing agents, request configuration, and load balancing
- **Multiple Bind Addresses**: Coordinator can bind to multiple IP addresses and ports simultaneously
- **Metrics & Monitoring**: Prometheus metrics with Grafana dashboards
- **IPv6 Support**: Automatic detection and utilization of IPv6 addresses
- **Round-Robin Load Balancing**: Distributes requests across available IPs
- **REST API**: Full API for system management and request execution
- **WebSocket Communication**: Real-time agent-coordinator communication
- **Request History**: Tracks all executed requests with metadata
- **Agent Reconnection**: Automatic reconnection with exponential backoff when coordinator restarts

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start the Coordinator

```bash
# Single bind address
python main.py --mode coordinator --host 0.0.0.0 --port 8000

# Multiple bind addresses
python main.py --mode coordinator --host 0.0.0.0 --port 8000 \
  --bind 192.168.1.100:8000 \
  --bind [::1]:8001 \
  --bind 10.0.0.50
```

### Start an Agent

```bash
python main.py --mode agent --coordinator-url http://localhost:8000 --agent-id agent-01
```

If no agent ID is provided, one will be auto-generated.

### Start Monitoring Stack

```bash
# Start the monitoring stack (Prometheus + Grafana)
docker-compose -f docker-compose.monitoring.yml up -d

# Access Grafana dashboard
open http://localhost:3000
# Default login: admin/admin
```

## API Endpoints

### Agent Management
- `POST /api/agents/register` - Register a new agent
- `GET /api/agents` - List all agents
- `DELETE /api/agents/{agent_id}` - Remove an agent

### Request Configuration
- `POST /api/config/request` - Configure the HTTP request
- `GET /api/config/request` - Get current request configuration

### Request Execution
- `POST /api/execute` - Execute a custom HTTP request using round-robin

### Monitoring
- `GET /api/pool/status` - Get IP pool status
- `GET /api/stats` - Get system statistics
- `GET /api/history` - Get request history
- `GET /metrics` - Prometheus metrics endpoint

## Environment Variables

You can configure the application using environment variables with the `DISPATCHER_` prefix:

- `DISPATCHER_MODE` - Application mode (agent/coordinator/monitoring)
- `DISPATCHER_COORDINATOR_URL` - URL of the coordinator
- `DISPATCHER_AGENT_ID` - Agent identifier
- `DISPATCHER_LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)

## Legacy Monitoring TUI (Deprecated)

The legacy monitoring mode is deprecated in favor of Grafana dashboards:

```bash
# Deprecated - use Grafana instead
python main.py --mode monitoring --coordinator-url http://localhost:8000
```

## Architecture

1. **Agents** connect to the Coordinator via WebSocket and report their IPv6 addresses
2. **Coordinator** maintains a pool of available IPs and distributes requests using round-robin
3. **Monitoring** provides a real-time view of the system state and allows manual control
4. Requests are executed by agents using specific source IPv6 addresses
5. All communication is asynchronous for optimal performance

## Multiple Bind Addresses

The coordinator can bind to multiple network interfaces simultaneously:

```bash
# Bind to multiple specific IPs
python main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind 192.168.1.100:8000 \
  --bind 10.0.0.50:8001

# Mix IPv4 and IPv6
python main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind [::1]:8000 \
  --bind 127.0.0.1:8001

# Same IP, different ports
python main.py --mode coordinator \
  --bind 0.0.0.0:8000 \
  --bind 0.0.0.0:8001 \
  --bind 0.0.0.0:8002
```

**Use cases:**
- Multi-homed servers with multiple network interfaces
- Load balancing across different network segments
- IPv4/IPv6 dual-stack deployments
- Development/testing with multiple local addresses

## Monitoring & Metrics

HTTP Dispatcher provides comprehensive monitoring through Prometheus metrics and Grafana dashboards.

### Available Metrics

- `http_dispatcher_requests_total` - Total requests executed (by agent, status code, method)
- `http_dispatcher_request_duration_seconds` - Request duration histogram (by agent, method)
- `http_dispatcher_agents_connected` - Number of connected agents
- `http_dispatcher_agents_total` - Total registered agents
- `http_dispatcher_ip_pool_size` - Size of the IP pool
- `http_dispatcher_ip_pool_available` - Available IPs in pool
- `http_dispatcher_websocket_connections` - Active WebSocket connections
- `http_dispatcher_request_errors_total` - Request errors (by agent, error type)
- `http_dispatcher_agent_requests_total` - Total requests per agent
- `http_dispatcher_response_size_bytes` - Response size histogram (by agent)
- `http_dispatcher_queue_depth` - Pending requests in queue (by agent)
- `http_dispatcher_uptime_seconds` - Coordinator uptime

### Quick Start Monitoring

1. **Start the coordinator:**
   ```bash
   python main.py --mode coordinator --host 0.0.0.0 --port 8000
   ```

2. **Start monitoring stack:**
   ```bash
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

3. **Access dashboards:**
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - Alertmanager: http://localhost:9093
   - Metrics endpoint: http://localhost:8000/metrics

### Dashboard Features

The production Grafana dashboard includes:

**System Overview:**
- Active agents, available IPs, total request rate, success rate
- P95 latency, total requests, error rate, WebSocket connections

**Request Metrics:**
- Request rate by agent with aggregated totals
- Status code breakdown (2xx, 4xx, 5xx)
- Response time percentiles (50th, 95th, 99th)
- Error rates by agent and error type

**Agent Performance:**
- Performance comparison table (rate, duration, success rate)
- Request distribution by HTTP method
- Total requests by agent (pie chart)

**System Health:**
- Agent and WebSocket connection status
- IP pool utilization over time
- Request volume trends (1h increases)

**Alerting:**
- High error rate (>5%)
- No agents connected
- Low IP pool availability (<20%)
- High response times (>10s)
- Request timeouts

## API Usage Examples

### Execute Custom Request

The execute endpoint accepts a POST request with custom configuration:

```bash
# Simple GET request
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.github.com/user",
    "method": "GET",
    "headers": {
      "User-Agent": "HTTP-Dispatcher",
      "Accept": "application/json"
    },
    "timeout": 30.0
  }'

# POST request with payload
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.example.com/data",
    "method": "POST",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer your-token"
    },
    "body": {
      "message": "Hello from HTTP Dispatcher",
      "timestamp": "2024-01-01T00:00:00Z"
    },
    "timeout": 45.0
  }'

# PUT request with custom headers
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.example.com/users/123",
    "method": "PUT",
    "headers": {
      "Content-Type": "application/json",
      "X-API-Key": "your-api-key"
    },
    "body": {
      "name": "Updated Name",
      "email": "new@example.com"
    }
  }'
```

### Request Configuration (Legacy)

You can still configure a default request that gets stored on the server:

```json
{
  "url": "https://api.example.com/endpoint",
  "method": "GET",
  "headers": {
    "User-Agent": "HTTP-Dispatcher",
    "Accept": "application/json"
  },
  "timeout": 30.0
}
```