# Environment Variables Reference

**Last Updated: 2026-03-17**

Complete reference for all AMC-Grid environment variables, grouped by category.

## Overview

AMC-Grid uses environment variables for configuration via `.env` files (loaded by `python-dotenv`). The system has sensible defaults and works without any API keys (heuristic mode).

## Setup

```bash
# Copy example configuration
cp .env.example .env

# Edit and add your values
nano .env

# Verify configuration loaded
cat .env | grep -E "^[A-Z_]+" | head -20
```

## Variable Categories

### LLM / AI Provider Keys

These enable LLM-backed agent reasoning. Without them, agents use built-in heuristics.

| Variable | Type | Required | Default | Format | Description |
|----------|------|----------|---------|--------|-------------|
| `OPENAI_API_KEY` | String | No | (empty) | `sk-...` | OpenAI API key for GPT models |
| `ANTHROPIC_API_KEY` | String | No | (empty) | `claude-...` or `sk-ant-...` | Anthropic Claude API key |
| `GEMINI_API_KEY` | String | No | (empty) | `AIza...` | Google Gemini API key (primary LLM) |

**LLM Fallback Chain**:
1. Google Gemini (if `GEMINI_API_KEY` set)
2. Anthropic Claude (if `ANTHROPIC_API_KEY` set)
3. Ollama local (if available, requires Docker)
4. Heuristic mode (always available, no key needed)

**Usage**:
```bash
# Agents will automatically detect and use available keys
# No code changes required

# Test LLM fallback (check logs)
./amc-grid.sh 2>&1 | grep -i "inference\|provider"
```

### Server Configuration

Control how the FastAPI backend runs.

| Variable | Type | Required | Default | Valid Values | Description |
|----------|------|----------|---------|--------------|-------------|
| `HOST` | String | No | `0.0.0.0` | Any IP address | Server bind address |
| `PORT` | Integer | No | `8000` | 1-65535 | Server port |
| `LOG_LEVEL` | String | No | `INFO` | DEBUG, INFO, WARNING, ERROR, CRITICAL | Logging verbosity |
| `UVICORN_WORKERS` | Integer | No | `1` | 1+ | Number of worker processes |

**Usage Examples**:

```bash
# Run on different port (if 8000 in use)
PORT=8001 ./venv/bin/python3 src/python/api_main.py

# Enable debug logging
LOG_LEVEL=DEBUG ./amc-grid.sh

# Check if port is available before starting
lsof -i :8000  # Should show nothing if port is free
```

### Simulation Configuration

Control simulation behavior and speed.

| Variable | Type | Required | Default | Valid Values | Description |
|----------|------|----------|---------|--------------|-------------|
| `SIMULATION_HZ` | Integer | No | `10` | 1-60 | Simulation tick rate (updates per second) |
| `DEFAULT_THEATER` | String | No | `romania` | romania, south_china_sea, baltic | Initial scenario to load |

**Usage Examples**:

```bash
# Run faster simulation (higher CPU usage)
SIMULATION_HZ=20 ./amc-grid.sh

# Start with different theater
DEFAULT_THEATER=south_china_sea ./amc-grid.sh

# Available theaters (see theaters/ directory)
ls theaters/*.yaml
```

### WebSocket Configuration

Control client connectivity and backend URL.

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `WS_BACKEND_URL` | String | No | `ws://localhost:8000/ws` | WebSocket endpoint URL (used by frontend + simulator) |

**Usage**:
```bash
# Change if backend is on different host
WS_BACKEND_URL=ws://192.168.1.100:8000/ws ./amc-grid.sh

# Or if using HTTPS
WS_BACKEND_URL=wss://api.example.com/ws ./amc-grid.sh
```

### Optional: Performance Tuning

Advanced settings for production deployments.

| Variable | Type | Default | Impact |
|----------|------|---------|--------|
| `MAX_WS_CONNECTIONS` | Integer | 20 | Max WebSocket clients allowed (edit in code) |
| `RATE_LIMIT_MAX_MESSAGES` | Integer | 30 | Max WebSocket messages per second per client (edit in code) |

To modify these, edit `src/python/api_main.py`:
```python
MAX_WS_CONNECTIONS = 20  # Line ~43
RATE_LIMIT_MAX_MESSAGES = 30  # Line ~44
```

## Environment Validation

AMC-Grid validates configuration on startup:

```bash
# Check if .env is valid
./venv/bin/python3 -c "
from src.python.config import load_settings
s = load_settings()
print(f'Host: {s.host}')
print(f'Port: {s.port}')
print(f'LLM Providers: {s.openai_api_key[:3] if s.openai_api_key else \"None\"}...')
"
```

## Example Configurations

### Development (No LLM)

```bash
# .env
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=DEBUG
SIMULATION_HZ=10
DEFAULT_THEATER=romania

# No API keys — use heuristic agents only
```

### Development (With LLM)

```bash
# .env
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
SIMULATION_HZ=10
DEFAULT_THEATER=romania

# Add API keys for LLM reasoning
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=claude-...
```

### Production Deployment

```bash
# .env (on production server)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=WARNING  # Less verbose
SIMULATION_HZ=10
DEFAULT_THEATER=romania

# Use environment variable secrets (never commit)
OPENAI_API_KEY=${OPENAI_API_KEY}  # Set via deployment platform
GEMINI_API_KEY=${GEMINI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
WS_BACKEND_URL=wss://api.example.com/ws  # HTTPS for production
```

### Docker Environment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

ENV HOST=0.0.0.0
ENV PORT=8000
ENV LOG_LEVEL=INFO
ENV SIMULATION_HZ=10

# API keys passed at runtime, not in Dockerfile
CMD ["python", "-m", "uvicorn", "src.python.api_main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

Run with:
```bash
docker run -e OPENAI_API_KEY=sk-... \
           -e GEMINI_API_KEY=AIza... \
           -p 8000:8000 \
           amc-grid:latest
```

### Kubernetes Deployment

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: amc-grid-config
data:
  HOST: "0.0.0.0"
  PORT: "8000"
  LOG_LEVEL: "INFO"
  SIMULATION_HZ: "10"
  DEFAULT_THEATER: "romania"
---
apiVersion: v1
kind: Secret
metadata:
  name: amc-grid-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  GEMINI_API_KEY: "AIza..."
  ANTHROPIC_API_KEY: "claude-..."
```

## Troubleshooting

### "API key not found" warning

**Symptom**: Logs show "Missing OPENAI_API_KEY"

**Cause**: API key not set in `.env` or environment

**Fix**:
```bash
# Add to .env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# Or set directly
export OPENAI_API_KEY=sk-...
./amc-grid.sh

# Verify
grep OPENAI .env
```

### Backend binds to wrong interface

**Symptom**: Can't connect to `localhost:8000` from another machine

**Cause**: `HOST` set to `127.0.0.1` instead of `0.0.0.0`

**Fix**:
```bash
# Check current setting
grep "^HOST=" .env

# Change to allow all interfaces
sed -i '' 's/HOST=.*/HOST=0.0.0.0/' .env

# Restart
./amc-grid.sh
```

### "Port already in use"

**Symptom**: `Address already in use: ('0.0.0.0', 8000)`

**Fix**:
```bash
# Find process on port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use different port
echo "PORT=8001" >> .env
./amc-grid.sh  # Now runs on :8001
```

### Frontend can't connect to backend

**Symptom**: "Connecting..." in browser, never connects

**Check**:
```bash
# Verify backend is running
curl http://localhost:8000/api/theaters

# Check WS_BACKEND_URL is correct
grep WS_BACKEND_URL .env

# If backend is on different host
echo "WS_BACKEND_URL=ws://192.168.1.100:8000/ws" >> .env
# Then refresh browser
```

## Environment Variable Reference by Use Case

### For Testing

```bash
# Unit tests (no special vars needed)
./venv/bin/python3 -m pytest src/python/tests/

# E2E tests with live backend
AMC_GRID_LIVE=1 npm run test:e2e:live
```

### For Debugging

```bash
# Maximum logging
LOG_LEVEL=DEBUG ./amc-grid.sh

# Check config loaded correctly
./venv/bin/python3 -c "
from dotenv import load_dotenv; load_dotenv()
import os
for k, v in os.environ.items():
    if k.isupper() and not k.startswith('_'):
        print(f'{k}={v}')
"
```

### For Performance Testing

```bash
# Faster simulation for load testing
SIMULATION_HZ=60 ./amc-grid.sh

# Monitor resource usage
watch -n 0.1 'ps aux | grep api_main | grep -v grep'
```

## Changing Configuration at Runtime

Most configuration must be set before startup. For changes:

```bash
# 1. Stop backend
Ctrl+C

# 2. Edit .env
nano .env

# 3. Restart
./amc-grid.sh
```

For theater changes without restart:
```bash
# Use API endpoint instead
curl -X POST http://localhost:8000/api/theater \
  -H "Content-Type: application/json" \
  -d '{"theater": "south_china_sea"}'

# No restart needed — simulation state resets
```

## Security Notes

**NEVER**:
- Commit `.env` files to Git
- Hardcode API keys in source code
- Log API keys in debug output
- Expose `.env` in error messages

**ALWAYS**:
- Use `.gitignore` to exclude `.env`
- Store secrets in environment variables or secure vaults
- Rotate API keys regularly
- Use scoped credentials (limited permissions)

Example `.gitignore`:
```
.env
.env.local
.env.*.local
```
