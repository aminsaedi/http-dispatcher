# Tailscale Integration Guide

HTTP Dispatcher has built-in Tailscale support that makes installation and networking significantly easier!

## Why Tailscale?

✅ **Zero Configuration** - No port forwarding, firewall rules, or complex networking  
✅ **Auto-Discovery** - Agents automatically find the coordinator  
✅ **Secure by Default** - All traffic encrypted via Tailscale VPN  
✅ **Easy Access** - Use friendly hostnames instead of IPs  
✅ **Works Everywhere** - Same setup works on any network  

## Installation with Tailscale

### Coordinator Setup

1. **Install Tailscale** on your coordinator server:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. **Install HTTP Dispatcher Coordinator:**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- coordinator
   ```

   The installer will automatically:
   - Detect your Tailscale hostname and IP
   - Bind the coordinator to your Tailscale IP
   - Configure monitoring to use Tailscale networking

### Agent Setup

1. **Install Tailscale** on each agent node:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. **Install HTTP Dispatcher Agent** (no coordinator URL needed!):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/aminsaedi/http-dispatcher/main/install.sh | sudo bash -s -- agent
   ```

   The installer will:
   - Auto-detect your coordinator by scanning Tailscale hosts
   - Use Tailscale hostnames for connection
   - Configure secure networking automatically

## How Auto-Detection Works

The installer looks for common coordinator hostnames in your Tailscale network:
- `coordinator`
- `http-dispatcher-coordinator`
- `dispatcher-coordinator`
- `server`
- `dispatcher`

If your coordinator has one of these hostnames, agents will find it automatically!

## Manual Configuration

If auto-detection doesn't work, you can specify the coordinator manually:

```bash
# Using Tailscale hostname
curl -fsSL ... | sudo bash -s -- agent --coordinator-url http://my-coordinator-hostname:8000

# Using Tailscale IP
curl -fsSL ... | sudo bash -s -- agent --coordinator-url http://100.x.x.x:8000
```

## Accessing Services via Tailscale

Once installed, you can access services from any Tailscale-connected device:

### Coordinator API
```bash
# Using hostname
curl http://coordinator-hostname:8000/api/stats

# Using Tailscale IP
curl http://100.x.x.x:8000/api/stats
```

### Monitoring Dashboards
- **Grafana**: `http://coordinator-hostname:3000` (admin/admin)
- **Prometheus**: `http://coordinator-hostname:9090`
- **Metrics**: `http://coordinator-hostname:8000/metrics`

## Network Configuration

### Docker Containers

All monitoring containers use `network_mode: host` to access Tailscale networking directly. This means:
- Prometheus can scrape metrics via Tailscale
- Grafana is accessible via Tailscale
- No complex Docker networking configuration needed

### Coordinator Binding

The coordinator binds to:
- `0.0.0.0:8000` - Accessible from all interfaces
- `TAILSCALE_IP:8000` - Explicitly accessible via Tailscale

This ensures the coordinator is reachable both locally and via Tailscale.

## Troubleshooting

### Agent Can't Find Coordinator

1. **Check Tailscale status:**
   ```bash
   tailscale status
   ```

2. **Verify coordinator is online:**
   ```bash
   tailscale ping coordinator-hostname
   ```

3. **Check coordinator is running:**
   ```bash
   curl http://coordinator-hostname:8000/api/stats
   ```

4. **Manually specify coordinator:**
   ```bash
   sudo systemctl edit http-dispatcher-agent
   # Add: Environment="DISPATCHER_COORDINATOR_URL=http://coordinator-hostname:8000"
   sudo systemctl daemon-reload
   sudo systemctl restart http-dispatcher-agent
   ```

### Prometheus Can't Scrape Metrics

1. **Check Prometheus config:**
   ```bash
   cat /opt/http-dispatcher/monitoring/prometheus.yml
   ```

2. **Verify coordinator is accessible:**
   ```bash
   curl http://coordinator-hostname:8000/metrics
   ```

3. **Update Prometheus config if needed:**
   ```bash
   sudo nano /opt/http-dispatcher/monitoring/prometheus.yml
   # Update target to use coordinator Tailscale hostname or IP
   sudo systemctl restart http-dispatcher-monitoring
   ```

### Coordinator Not Accessible via Tailscale

1. **Check Tailscale IP:**
   ```bash
   tailscale ip -4
   ```

2. **Verify binding:**
   ```bash
   sudo netstat -tlnp | grep 8000
   ```

3. **Check firewall (if any):**
   ```bash
   # Tailscale should handle this, but verify
   sudo tailscale status
   ```

## Best Practices

1. **Use Descriptive Hostnames** - Name your coordinator something like `http-dispatcher-coordinator` for easy discovery

2. **Keep Tailscale Updated** - Regularly update Tailscale for security and performance

3. **Monitor Tailscale Status** - Use `tailscale status` to verify all nodes are connected

4. **Use Tailscale ACLs** - Configure access control lists for additional security

5. **Backup Tailscale Keys** - Keep your Tailscale auth keys safe

## Security Considerations

- ✅ All traffic is encrypted via Tailscale
- ✅ No ports need to be exposed to the internet
- ✅ Access control via Tailscale ACLs
- ✅ Automatic key rotation
- ✅ Audit logs available in Tailscale admin console

## Example Setup

```bash
# On coordinator server (hostname: coordinator)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
curl -fsSL ... | sudo bash -s -- coordinator

# On agent 1 (hostname: agent-1)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
curl -fsSL ... | sudo bash -s -- agent

# On agent 2 (hostname: agent-2)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
curl -fsSL ... | sudo bash -s -- agent
```

That's it! All agents automatically connect to the coordinator via Tailscale. 🎉

