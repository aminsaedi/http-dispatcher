# Configuration Guide

## Coordinator Interface Binding

The coordinator can listen on multiple network interfaces simultaneously. This is useful for:
- Multi-homed servers with multiple network interfaces
- Separating internal and external traffic
- IPv4/IPv6 dual-stack deployments
- Tailscale and local network access

## Configuration Methods

### 1. During Installation

Specify bind addresses during installation:

```bash
# Bind to specific IPs
sudo bash install.sh coordinator \
  --bind 192.168.1.100:8000 \
  --bind 10.0.0.50:8000

# Bind to IPv6 addresses
sudo bash install.sh coordinator \
  --bind [::1]:8000 \
  --bind [2001:db8::1]:8000

# Mix IPv4 and IPv6
sudo bash install.sh coordinator \
  --bind 192.168.1.100:8000 \
  --bind [::1]:8001

# Different ports on same interface
sudo bash install.sh coordinator \
  --bind 0.0.0.0:8000 \
  --bind 0.0.0.0:8001 \
  --bind 0.0.0.0:8002
```

### 2. After Installation (Systemd Override)

Edit the systemd service to add bind addresses:

```bash
# Create override directory
sudo systemctl edit http-dispatcher-coordinator
```

Add or modify the `ExecStart` line:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind 192.168.1.100:8000 \
  --bind 10.0.0.50:8000 \
  --bind [::1]:8000
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-coordinator
```

### 3. Direct Service File Edit

Edit the service file directly:

```bash
sudo nano /etc/systemd/system/http-dispatcher-coordinator.service
```

Modify the `ExecStart` line:

```ini
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind 192.168.1.100:8000 \
  --bind 10.0.0.50:8000
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-coordinator
```

## Common Configurations

### Listen on All Interfaces (Default)

```bash
# Default behavior - listens on 0.0.0.0 (all IPv4 interfaces)
--host 0.0.0.0 --port 8000
```

### Listen Only on Localhost

```bash
--host 127.0.0.1 --port 8000
# or
--host localhost --port 8000
```

### Listen on Specific Interface

```bash
# Get your interface IP
ip addr show

# Bind to specific IP
--host 0.0.0.0 --port 8000 --bind 192.168.1.100:8000
```

### Tailscale + Local Network

```bash
# Auto-detected during installation, or manually:
--host 0.0.0.0 --port 8000 --bind 100.x.x.x:8000
```

### IPv6 Only

```bash
--host [::] --port 8000
# or specific IPv6 address
--host [::] --port 8000 --bind [2001:db8::1]:8000
```

### Multiple Ports on Same Interface

```bash
--host 0.0.0.0 --port 8000 \
  --bind 0.0.0.0:8001 \
  --bind 0.0.0.0:8002
```

## Finding Your Interface IPs

### List All IP Addresses

```bash
# Linux
ip addr show
# or
ifconfig

# macOS
ifconfig | grep "inet "

# Show only IPv4
ip -4 addr show

# Show only IPv6
ip -6 addr show
```

### Find Tailscale IP

```bash
tailscale ip -4
tailscale ip -6
```

### Find Interface by Name

```bash
# Find IP for specific interface (e.g., eth0)
ip addr show eth0

# Find IP for Tailscale interface
ip addr show tailscale0
```

## Verification

After configuring, verify the coordinator is listening on the correct interfaces:

```bash
# Check listening ports
sudo netstat -tlnp | grep 8000
# or
sudo ss -tlnp | grep 8000

# Test connectivity
curl http://192.168.1.100:8000/api/stats
curl http://10.0.0.50:8000/api/stats

# Check service status
http-dispatcher coordinator status

# View logs
http-dispatcher coordinator logs
```

## Examples

### Example 1: Multi-Homed Server

Server with two network interfaces:
- `eth0`: 192.168.1.100 (internal network)
- `eth1`: 10.0.0.50 (DMZ network)

```bash
sudo systemctl edit http-dispatcher-coordinator
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind 192.168.1.100:8000 \
  --bind 10.0.0.50:8000
```

### Example 2: Tailscale + Local Network

```bash
sudo systemctl edit http-dispatcher-coordinator
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind 100.64.1.2:8000
```

### Example 3: IPv6 Dual-Stack

```bash
sudo systemctl edit http-dispatcher-coordinator
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator \
  --host 0.0.0.0 --port 8000 \
  --bind [::1]:8000 \
  --bind [2001:db8::1]:8000
```

## Troubleshooting

### Service Won't Start

Check logs for binding errors:

```bash
sudo journalctl -u http-dispatcher-coordinator -n 50
```

Common issues:
- **Address already in use**: Another service is using the port
- **Permission denied**: Binding to privileged ports (<1024) requires root
- **Invalid address**: Check IP address format

### Can't Connect to Specific Interface

1. **Verify interface is up:**
   ```bash
   ip link show eth0
   ```

2. **Check firewall rules:**
   ```bash
   sudo iptables -L -n
   sudo ufw status
   ```

3. **Test connectivity:**
   ```bash
   curl -v http://interface-ip:8000/api/stats
   ```

### Port Already in Use

Find what's using the port:

```bash
sudo lsof -i :8000
# or
sudo netstat -tlnp | grep 8000
```

Kill the process or change the coordinator port.

## Environment Variables

You can also use environment variables (though systemd override is preferred):

```bash
sudo systemctl edit http-dispatcher-coordinator
```

```ini
[Service]
Environment="DISPATCHER_BIND_ADDRESSES=192.168.1.100:8000,10.0.0.50:8000"
```

Note: This requires code changes to support environment variable parsing.

