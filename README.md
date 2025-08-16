# HTTP Dispatcher

A distributed HTTP request system with IPv6 support, featuring agent-based request distribution, round-robin load balancing, and a TUI monitoring interface.

## Features

- **Agent Mode**: Outbound gateway nodes that execute HTTP requests using specific IPv6 addresses
- **Coordinator Mode**: Central server managing agents, request configuration, and load balancing
- **Monitoring Mode**: Terminal UI for system management and monitoring
- **IPv6 Support**: Automatic detection and utilization of IPv6 addresses
- **Round-Robin Load Balancing**: Distributes requests across available IPs
- **REST API**: Full API for system management and request execution
- **WebSocket Communication**: Real-time agent-coordinator communication
- **Request History**: Tracks all executed requests with metadata

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Start the Coordinator

```bash
python main.py --mode coordinator --host 0.0.0.0 --port 8000
```

### Start an Agent

```bash
python main.py --mode agent --coordinator-url http://localhost:8000 --agent-id agent-01
```

If no agent ID is provided, one will be auto-generated.

### Start the Monitoring TUI

```bash
python main.py --mode monitoring --coordinator-url http://localhost:8000
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
- `GET /api/execute` - Execute the configured request using round-robin

### Monitoring
- `GET /api/pool/status` - Get IP pool status
- `GET /api/stats` - Get system statistics
- `GET /api/history` - Get request history

## Environment Variables

You can configure the application using environment variables with the `DISPATCHER_` prefix:

- `DISPATCHER_MODE` - Application mode (agent/coordinator/monitoring)
- `DISPATCHER_COORDINATOR_URL` - URL of the coordinator
- `DISPATCHER_AGENT_ID` - Agent identifier
- `DISPATCHER_LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)

## Monitoring TUI Shortcuts

- `q` - Quit
- `r` - Refresh data
- `e` - Execute request
- `c` - Configure request
- Tab navigation between panels

## Architecture

1. **Agents** connect to the Coordinator via WebSocket and report their IPv6 addresses
2. **Coordinator** maintains a pool of available IPs and distributes requests using round-robin
3. **Monitoring** provides a real-time view of the system state and allows manual control
4. Requests are executed by agents using specific source IPv6 addresses
5. All communication is asynchronous for optimal performance

## Example Request Configuration

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