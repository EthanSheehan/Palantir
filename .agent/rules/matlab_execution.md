---
description: "Instructions for executing MATLAB code. Agent MUST run scripts."
globs: ["**/*.m"]
---

# MATLAB Execution

## Overview

We execute MATLAB code via the standard VS Code terminal or the MATLAB extension. **The Agent MUST execute MATLAB verification scripts directly.**

## Agent Execution (Verified)

Use the following command pattern. If `matlab` is not in the PATH, check standard locations first.

```bash
# 1. Try standard command
matlab -batch "run('src/matlab/script_name.m');"

# 2. If failed, use discovered path (macOS):
/Applications/MATLAB_R2025b.app/bin/matlab -batch "run('src/matlab/script_name.m');"
```

## Best Practice

- **Always** run simple test scripts to verify logic before claiming a task is done.
- If multiple verifications are needed, consider creating a `tests/run_all_tests.m` runner.

## Simulink

- Use `run_sim.m` wrappers to execute models headless.
