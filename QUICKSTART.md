# HTTP Dispatcher - Quick Start Guide

## 🚀 One-Liner Installation

### Coordinator (Server)
```bash
curl -fsSL https://raw.githubusercontent.com/your-repo/http-dispatcher/main/install.sh | sudo bash -s -- coordinator
```

### Agent (Client)

**With Tailscale (Recommended - Auto-detects coordinator!):**
```bash
# Just run this - coordinator is auto-detected!
curl -fsSL https://raw.githubusercontent.com/your-repo/http-dispatcher/main/install.sh | sudo bash -s -- agent
```

**Without Tailscale:**
```bash
curl -fsSL https://raw.githubusercontent.com/your-repo/http-dispatcher/main/install.sh | sudo bash -s -- agent --coordinator-url http://YOUR_COORDINATOR_IP:8000
```

## 🎯 Tailscale Makes It Easy!

If you use **Tailscale**, the installer automatically:
- Finds your coordinator (no need to specify URL)
- Configures secure networking
- Sets up monitoring connections
- Uses friendly hostnames instead of IPs

Just install and it works! 🎉

## 📋 What You Get

✅ **Automatic Service Management** - No more tmux! Services run as systemd units  
✅ **Auto-Restart** - Services automatically restart on failure or reboot  
✅ **Integrated Monitoring** - Prometheus + Grafana automatically set up (coordinator only)  
✅ **Easy Management** - Simple commands to control everything  

## 🎮 Quick Commands

```bash
# Check status
http-dispatcher coordinator status
http-dispatcher agent status

# View logs
http-dispatcher coordinator logs
http-dispatcher agent logs

# Restart services
http-dispatcher coordinator restart
http-dispatcher agent restart

# Stop/Start
http-dispatcher coordinator stop
http-dispatcher coordinator start
```

## 🌐 Access Points (Coordinator)

After installation, access:
- **API**: http://localhost:8000
- **Metrics**: http://localhost:8000/metrics
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## 🔧 Configuration

### Change Coordinator Port
```bash
sudo systemctl edit http-dispatcher-coordinator
```
Add:
```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /opt/http-dispatcher/bin/main.py --mode coordinator --host 0.0.0.0 --port 9000
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-coordinator
```

### Change Agent Coordinator URL
```bash
sudo systemctl edit http-dispatcher-agent
```
Add:
```ini
[Service]
Environment="DISPATCHER_COORDINATOR_URL=http://new-coordinator:8000"
```
Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart http-dispatcher-agent
```

## 🐛 Troubleshooting

### Service won't start?
```bash
# Check status
sudo systemctl status http-dispatcher-coordinator

# View logs
sudo journalctl -u http-dispatcher-coordinator -n 50
```

### Agent can't connect?
```bash
# Test coordinator
curl http://coordinator-ip:8000/api/stats

# Check agent logs
http-dispatcher agent logs
```

### Monitoring not working?
```bash
# Check Docker
sudo systemctl status docker

# Check monitoring service
http-dispatcher monitoring status

# View container logs
docker logs prometheus
docker logs grafana
```

## 📚 More Information

- Full installation guide: [INSTALL.md](INSTALL.md)
- Complete documentation: [README.md](README.md)

