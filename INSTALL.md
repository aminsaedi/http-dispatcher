# HTTP Dispatcher Installation Guide

## Quick Start

### One-Liner Installation

**Install as Coordinator (with monitoring):**
```bash
curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- coordinator
```

**Install as Agent:**
```bash
curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- agent --coordinator-url http://coordinator-ip:8000
```

**With custom options:**
```bash
# Coordinator on custom port
curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- coordinator --port 9000

# Agent with custom ID
curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- agent --coordinator-url http://coordinator:8000 --agent-id my-agent-01
```

## Local Installation

If you have the repository locally:

```bash
# Navigate to the project directory
cd http-dispatcher

# Install as coordinator
sudo bash install.sh coordinator

# Install as agent
sudo bash install.sh agent --coordinator-url http://coordinator-ip:8000
```

## What Gets Installed

### Files and Directories
- `/opt/http-dispatcher/` - Main installation directory
  - `bin/main.py` - Main application script
  - `lib/src/` - Application source code
  - `monitoring/` - Monitoring configuration (coordinator only)
  - `etc/` - Configuration files

### Systemd Services
- `http-dispatcher-coordinator.service` - Coordinator service
- `http-dispatcher-agent.service` - Agent service
- `http-dispatcher-monitoring.service` - Monitoring stack (coordinator only)

### Management Command
- `/usr/local/bin/http-dispatcher` - Service management script

## Service Management

### Using the Management Script

```bash
# Check status
http-dispatcher coordinator status
http-dispatcher agent status
http-dispatcher monitoring status

# View logs (follow mode)
http-dispatcher coordinator logs
http-dispatcher agent logs

# Control services
http-dispatcher coordinator start
http-dispatcher coordinator stop
http-dispatcher coordinator restart

# Enable/disable auto-start
http-dispatcher coordinator enable
http-dispatcher coordinator disable
```

### Using systemd Directly

```bash
# Status
sudo systemctl status http-dispatcher-coordinator
sudo systemctl status http-dispatcher-agent
sudo systemctl status http-dispatcher-monitoring

# Control
sudo systemctl start http-dispatcher-coordinator
sudo systemctl stop http-dispatcher-coordinator
sudo systemctl restart http-dispatcher-coordinator

# Enable/disable
sudo systemctl enable http-dispatcher-coordinator
sudo systemctl disable http-dispatcher-coordinator

# View logs
sudo journalctl -u http-dispatcher-coordinator -f
sudo journalctl -u http-dispatcher-agent -f
```

## Configuration

### Coordinator Configuration

Edit the systemd service file to change coordinator settings:

```bash
sudo systemctl edit http-dispatcher-coordinator
```

Or edit directly:
```bash
sudo nano /etc/systemd/system/http-dispatcher-coordinator.service
```

Change the `ExecStart` line to modify host/port:
```ini
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator --host 0.0.0.0 --port 8000
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-coordinator
```

### Agent Configuration

Edit the systemd service file:
```bash
sudo systemctl edit http-dispatcher-agent
```

Or edit directly:
```bash
sudo nano /etc/systemd/system/http-dispatcher-agent.service
```

Change environment variables:
```ini
Environment="DISPATCHER_COORDINATOR_URL=http://coordinator-ip:8000"
Environment="DISPATCHER_AGENT_ID=my-agent-id"
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-agent
```

## Monitoring Setup

The monitoring stack is automatically installed and started when installing as coordinator. It includes:

- **Prometheus** - Metrics collection (port 9090)
- **Grafana** - Dashboards (port 3000, default login: admin/admin)
- **Node Exporter** - System metrics (port 9100)
- **Alertmanager** - Alert handling (port 9093)

### Access Monitoring

- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Metrics endpoint: http://localhost:8000/metrics

### Prometheus Configuration

If your coordinator is not accessible via `host.docker.internal`, edit the Prometheus config:

```bash
sudo nano /opt/http-dispatcher/monitoring/prometheus.yml
```

Update the target to use your coordinator's IP:
```yaml
- job_name: 'http-dispatcher'
  static_configs:
    - targets: ['YOUR_COORDINATOR_IP:8000']
```

Then restart monitoring:
```bash
http-dispatcher monitoring restart
```

## Troubleshooting

### Service Won't Start

1. Check service status:
   ```bash
   sudo systemctl status http-dispatcher-coordinator
   ```

2. Check logs:
   ```bash
   sudo journalctl -u http-dispatcher-coordinator -n 50
   ```

3. Verify Python installation:
   ```bash
   python3 --version
   which python3
   ```

4. Check file permissions:
   ```bash
   ls -la /opt/http-dispatcher
   sudo chown -R http-dispatcher:http-dispatcher /opt/http-dispatcher
   ```

### Agent Can't Connect to Coordinator

1. Verify coordinator is running:
   ```bash
   curl http://coordinator-ip:8000/api/stats
   ```

2. Check network connectivity:
   ```bash
   ping coordinator-ip
   telnet coordinator-ip 8000
   ```

3. Check agent logs:
   ```bash
   http-dispatcher agent logs
   ```

4. Verify coordinator URL in agent service:
   ```bash
   sudo systemctl show http-dispatcher-agent | grep COORDINATOR
   ```

### Monitoring Not Working

1. Check if Docker is running:
   ```bash
   sudo systemctl status docker
   ```

2. Check monitoring service:
   ```bash
   http-dispatcher monitoring status
   ```

3. Check Docker containers:
   ```bash
   docker ps
   docker logs prometheus
   docker logs grafana
   ```

4. Verify Prometheus can reach coordinator:
   ```bash
   docker exec prometheus wget -qO- http://host.docker.internal:8000/metrics
   ```

## Uninstallation

To remove HTTP Dispatcher:

```bash
# Stop and disable services
sudo systemctl stop http-dispatcher-coordinator
sudo systemctl stop http-dispatcher-agent
sudo systemctl stop http-dispatcher-monitoring
sudo systemctl disable http-dispatcher-coordinator
sudo systemctl disable http-dispatcher-agent
sudo systemctl disable http-dispatcher-monitoring

# Remove service files
sudo rm /etc/systemd/system/http-dispatcher-*.service
sudo systemctl daemon-reload

# Remove installation
sudo rm -rf /opt/http-dispatcher
sudo rm /usr/local/bin/http-dispatcher

# Remove service user (optional)
sudo userdel http-dispatcher
```

## Upgrading

To upgrade to a new version:

```bash
# Stop services
sudo systemctl stop http-dispatcher-coordinator
sudo systemctl stop http-dispatcher-agent

# Backup current installation
sudo cp -r /opt/http-dispatcher /opt/http-dispatcher.backup

# Run installation script again (it will update files)
sudo bash install.sh coordinator

# Restart services
sudo systemctl start http-dispatcher-coordinator
sudo systemctl start http-dispatcher-agent
```

