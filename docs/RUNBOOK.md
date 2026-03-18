# Palantir C2 Operations Runbook

**Last Updated: 2026-03-17**

This guide covers deployment, health checks, monitoring, common issues, and rollback procedures for Palantir C2.

## System Overview

Palantir is a three-component system:

1. **FastAPI Backend** (`:8000`) — WebSocket server, simulation engine, AI agents
2. **Cesium Frontend** (`:3000`) — 3D tactical visualization
3. **Drone Simulator** — Optional UAV telemetry generator

All three launch with `./palantir.sh` but can run independently for testing.

## Pre-Deployment Checklist

- [ ] Python 3.10+ installed and verified
- [ ] Virtual environment created and activated (`./venv/bin/python3 --version`)
- [ ] Dependencies installed (`./venv/bin/pip install -r requirements.txt`)
- [ ] `.env` file created with required API keys (or copied from `.env.example`)
- [ ] Theater YAML configs validated (`theaters/*.yaml` exist and are readable)
- [ ] SSL certificates ready (if using HTTPS)
- [ ] Port 8000 and 3000 available (no processes listening)
- [ ] Adequate disk space for logs and data files

## Deployment Procedure

### Local/Development Deployment

```bash
# Verify prerequisites
python3 --version  # Should be 3.10+
ls -la venv/bin/python3
cat .env | grep -E "OPENAI|ANTHROPIC|GEMINI"  # Check API keys

# Launch all systems
./palantir.sh

# System ready when you see:
# ================================================
#   Backend:   http://localhost:8000
#   Dashboard: http://localhost:3000
#   API Docs:  http://localhost:8000/docs
# ================================================
```

### Production Deployment (Docker)

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/python src/python
COPY src/frontend src/frontend
COPY theaters theaters
COPY .env .

# Expose ports
EXPOSE 8000 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/theaters || exit 1

# Run backend (frontend served separately via nginx)
CMD ["python", "-m", "uvicorn", "src.python.api_main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: palantir-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: palantir
  template:
    metadata:
      labels:
        app: palantir
    spec:
      containers:
      - name: backend
        image: palantir:latest
        ports:
        - containerPort: 8000
        env:
        - name: HOST
          value: "0.0.0.0"
        - name: PORT
          value: "8000"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: palantir-secrets
              key: openai-key
        livenessProbe:
          httpGet:
            path: /api/theaters
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/theaters
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

## Health Checks

### Backend Health Endpoint

```bash
# Check if backend is responding
curl -s http://localhost:8000/api/theaters | jq .

# Expected response:
# {"theaters": ["romania", "south_china_sea", "baltic"]}
```

### Full System Health Check

```bash
#!/bin/bash
# health_check.sh

echo "=== Backend Health ==="
curl -s http://localhost:8000/api/theaters > /dev/null && echo "✓ Backend API" || echo "✗ Backend API"

echo "=== Frontend Health ==="
curl -s http://localhost:3000 > /dev/null && echo "✓ Frontend" || echo "✗ Frontend"

echo "=== WebSocket Health ==="
# WebSocket requires a more sophisticated check (see WebSocket Testing below)

echo "=== Port Status ==="
lsof -i :8000 && echo "✓ Port 8000 in use" || echo "✗ Port 8000 free"
lsof -i :3000 && echo "✓ Port 3000 in use" || echo "✗ Port 3000 free"
```

### WebSocket Testing

```bash
# Use wscat for testing WebSocket connection
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8000/ws

# Expected: Connected message with simulation state (JSON)
# Send client type: {"client_type": "DASHBOARD"}
# Should receive state updates at 10Hz
```

## Monitoring and Logging

### Backend Logs

```bash
# Tail real-time logs
tail -f /tmp/palantir.log

# Filter by severity
grep "ERROR" /tmp/palantir.log
grep "WARNING" /tmp/palantir.log

# Check structlog output
cat /tmp/palantir.log | jq .  # Pretty-print JSON logs
```

### Key Log Messages

| Message | Severity | Meaning | Action |
|---------|----------|---------|--------|
| `Simulation running at 10Hz` | INFO | System healthy | None |
| `WebSocket client connected` | INFO | Dashboard/Simulator connected | Normal |
| `Detection confidence below threshold` | INFO | Sensor filtering working | None |
| `Agent inference failed, using heuristic` | WARNING | LLM provider down | Check `.env` keys |
| `WebSocket client limit exceeded` | WARNING | Too many clients | Increase `MAX_WS_CONNECTIONS` |
| `HITL nomination rejected` | WARNING | Strike board approval failed | Review operator action |
| `Theater loading failed` | ERROR | Configuration issue | Check `theaters/` directory |
| `Out of memory` | ERROR | Memory leak or insufficient resources | Restart system |

### Performance Metrics

Monitor these key metrics:

- **WebSocket message latency**: Should be <100ms
- **Simulation tick rate**: Should be consistent 10Hz
- **Memory usage**: Should stabilize (not continuously grow)
- **CPU usage**: Varies by agent load, usually 20-50%
- **Disk I/O**: Primarily during logging

## Common Issues and Fixes

### Issue: "Port already in use"

**Error message:**
```
ERROR: Address already in use: ('0.0.0.0', 8000)
```

**Fix:**
```bash
# Find process using port
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change port in .env
echo "PORT=8001" >> .env

# Restart
./palantir.sh
```

### Issue: WebSocket connection timeout

**Symptoms:** Frontend shows "Connecting..." but never connects

**Debugging:**
```bash
# Verify backend is running
curl -s http://localhost:8000/api/theaters

# Check WebSocket is accepting connections
wscat -c ws://localhost:8000/ws

# Verify .env WS_BACKEND_URL matches actual backend
cat .env | grep WS_BACKEND_URL
```

**Fix:**
```bash
# Update .env if backend is on different host
WS_BACKEND_URL=ws://actual-host:8000/ws

# Restart frontend
cd src/frontend && python3 -m http.server 3000
```

### Issue: "Agent inference failed" warnings

**Symptoms:** Logs show LLM provider errors

**Causes:**
- Missing API keys in `.env`
- API quota exceeded
- Network connectivity issue

**Fix:**
```bash
# Verify API keys are set
cat .env | grep "API_KEY"

# Test API connectivity
curl https://api.openai.com/v1/models  # with Authorization header

# System will fall back to heuristic mode automatically
# No action needed — heuristic agents work without API keys
```

### Issue: Memory continuously increases

**Symptoms:** `top` shows growing `%MEM`

**Causes:**
- WebSocket connection leak
- Unbounded list accumulation
- Circular reference preventing garbage collection

**Fix:**
```bash
# Check WebSocket connections
lsof -i :8000 | wc -l

# Restart backend to reset memory
killall python3
./venv/bin/python3 src/python/api_main.py

# For production: Set memory limits in Docker/Kubernetes
# Monitor with: watch -n 1 'ps aux | grep api_main'
```

### Issue: Tests fail with "Cannot import"

**Symptoms:**
```
ModuleNotFoundError: No module named 'src.python.agents'
```

**Fix:**
```bash
# Reinstall dependencies
./venv/bin/pip install -r requirements.txt

# Clear Python cache
find . -type d -name __pycache__ -exec rm -r {} +

# Try again
./venv/bin/python3 -m pytest src/python/tests/
```

### Issue: Frontend shows blank page

**Symptoms:** Browser at `:3000` shows empty/white screen

**Debugging:**
```bash
# Check browser console (F12 → Console)
# Look for JavaScript errors

# Verify frontend server is running
curl -s http://localhost:3000/index.html | head -20

# Check Cesium CDN is accessible
curl -s https://cesium.com/downloads/cesiumjs/releases/1.104/Cesium.js | head -5
```

**Fix:**
```bash
# Restart frontend server
cd src/frontend && python3 -m http.server 3000

# Clear browser cache: Ctrl+Shift+Delete → Clear All
# Or use hard refresh: Ctrl+Shift+R
```

## Rollback Procedures

### Rollback to Previous Version

```bash
# Identify last good commit
git log --oneline | head -10

# Checkout previous version
git checkout <good-commit-hash>

# Reinstall dependencies (in case requirements.txt changed)
./venv/bin/pip install -r requirements.txt

# Restart
./palantir.sh
```

### Rollback Database/Configuration

Palantir doesn't use a database (simulation is in-memory), but scenarios can be reset:

```bash
# Reload default theater configuration
POST http://localhost:8000/api/theater
{
  "theater": "romania"
}

# All state will be reset to initial configuration
```

### Rollback Feature Flags

If a feature causes issues, disable via environment:

```bash
# .env
# Disable HITL approval gates (allow strikes without approval)
HITL_ENABLED=false

# Disable certain agent types
AGENT_MODE=heuristic  # Use heuristics only, no LLM

# Restart
./palantir.sh
```

## Scaling Considerations

### Single Machine Limits

Current architecture supports:
- **WebSocket connections**: Up to 20 dashboard/simulator clients (configurable in `api_main.py`)
- **Simulation complexity**: 50+ UAVs, 100+ targets (depends on CPU)
- **Refresh rate**: 10Hz guaranteed (configurable in `.env`)

### Scaling Beyond Single Machine

For production scale:

1. **Separate frontend from backend**
   - Serve frontend via nginx/CDN
   - Backend API on separate container/machine

2. **Horizontal scaling (multiple backend instances)**
   - Use load balancer (nginx, HAProxy)
   - WebSocket sticky sessions required (route to same backend)
   - Shared state via Redis or database

3. **Agent scaling**
   - Run agents in separate workers (Celery, Ray)
   - Implement queue-based agent pipeline

4. **Simulation scaling**
   - Move `SimulationModel` to separate service
   - Implement distributed state synchronization

Example Redis-backed backend:

```python
# Use redis-py for distributed state
import redis

redis_client = redis.Redis(host='redis', port=6379)

# Store simulation state
redis_client.set('sim:state', json.dumps(simulation_state))

# Multiple backends can read/write to same state
```

## Maintenance Tasks

### Daily

- [ ] Check logs for ERRORs: `grep ERROR /tmp/palantir.log`
- [ ] Verify health: `curl http://localhost:8000/api/theaters`
- [ ] Monitor memory: `ps aux | grep api_main | grep -v grep`

### Weekly

- [ ] Rotate logs: `mv /tmp/palantir.log /tmp/palantir.log.$(date +%Y%m%d)`
- [ ] Review agent fallbacks: Check how often heuristics are used vs LLM
- [ ] Backup configurations: `tar czf theaters.backup.tar.gz theaters/`

### Monthly

- [ ] Review and archive logs
- [ ] Test rollback procedure
- [ ] Update dependencies: `./venv/bin/pip install -r requirements.txt --upgrade`
- [ ] Run full test suite: `./venv/bin/python3 -m pytest src/python/tests/`

## Performance Tuning

### Reduce WebSocket Latency

```env
# .env
SIMULATION_HZ=10  # Increase for faster updates (higher CPU)
```

### Reduce Memory Footprint

```python
# api_main.py
MAX_WS_CONNECTIONS = 5  # Reduce from 20
RATE_LIMIT_MAX_MESSAGES = 10  # Reduce from 30
```

### Reduce Agent Inference Time

```env
# .env
AGENT_MODE=heuristic  # Heuristics only (no LLM inference)
```

## Disaster Recovery

### Complete System Loss

```bash
# 1. Verify code is in Git (push all changes)
git push origin main

# 2. Clone fresh copy
cd ~/
git clone <repo-url>
cd Palantir

# 3. Recreate environment
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env

# 4. Restore API keys from secure store
# (Add OPENAI_API_KEY, etc. to .env)

# 5. Verify backup of theater configs
cp /backup/theaters/*.yaml theaters/

# 6. Start fresh
./palantir.sh
```

### Data Reconstruction

Palantir doesn't store persistent data (simulation is ephemeral), but scenarios can be reconstructed:

```bash
# All theater configurations are in source control
git log --follow theaters/

# Restore a previous scenario
git checkout <commit-hash> -- theaters/romania.yaml
```

## Support Resources

- **Code Issues**: Check [GitHub Issues](https://github.com/EthanSheehan/Palantir/issues)
- **Architecture**: Read [CLAUDE.md](../CLAUDE.md)
- **API Docs**: Visit `http://localhost:8000/docs` (when running)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Contacts

- **Project Lead**: Ethan Sheehan
- **Incident Channel**: [#palantir-incidents](https://example.com) (Slack)
