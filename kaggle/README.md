# Running backtests on Kaggle (free GPU)

Local runs are CPU-bound: on a 16 GB box already running other work, Ollama
falls back to CPU (`size_vram: 0`) and a 36-event HN backtest takes 6–10 hours.
A Kaggle T4 holds qwen2.5:7b Q4 (~4.7 GB) entirely in its 16 GB of VRAM, which
brings the same run under an hour.

**Before you start:** set the notebook's accelerator to **GPU T4 x2** (or P100)
and turn **Internet: On** in the sidebar. Internet is required — the notebook
installs Ollama and pulls the model over the network. Enabling it is a one-time
account phone-verification. Quotas change; check your account's current GPU
hours rather than trusting a number written here.

**Do not paste API keys into a Kaggle notebook.** These runs use a local Ollama
model and need no keys. If you ever want a Claude-backed run, use Kaggle
*Secrets* (Add-ons → Secrets), never an inline string.

---

## Cell 1 — install and start Ollama

```python
!curl -fsSL https://ollama.com/install.sh | sh

import subprocess, time, requests
subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _ in range(60):                      # wait for the server to accept connections
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        print("ollama up"); break
    except Exception:
        time.sleep(1)
else:
    raise RuntimeError("ollama did not start")
```

## Cell 2 — pull the model and confirm it is on the GPU

```python
!nvidia-smi --query-gpu=name,memory.total --format=csv
!ollama pull qwen2.5:7b

import requests
ps = requests.get("http://localhost:11434/api/ps").json()
# Force a load so /api/ps reports placement.
requests.post("http://localhost:11434/api/generate",
              json={"model": "qwen2.5:7b", "prompt": "hi", "stream": False,
                    "keep_alive": -1}, timeout=600)
for m in requests.get("http://localhost:11434/api/ps").json().get("models", []):
    vram = m.get("size_vram", 0)
    print(f"{m['name']}: size_vram={vram / 1e9:.2f} GB")
    assert vram > 0, "model landed on CPU — check the accelerator is enabled"
```

`size_vram > 0` is the check that matters. If it is 0 you are on CPU and the run
will be as slow as a laptop. `keep_alive: -1` pins the model so it is not
unloaded between events.

## Cell 3 — get the code and dependencies

```python
!git clone --depth 1 https://github.com/rajul-kk/LightningFish.git /kaggle/working/lf
!pip -q install anthropic openai scipy requests pytest

import os, sys
os.chdir("/kaggle/working/lf")
sys.path.insert(0, "/kaggle/working/lf")

# Only the engine and HN suites. The finance and service tests pull yfinance,
# praw, edgar, fastapi, modal and psycopg, none of which an HN run touches —
# installing them here would just cost GPU-session minutes.
!python -m pytest tests/core tests/hn -q 2>&1 | tail -3
```

That should report all green before you spend GPU time on a run. For the full
suite, add `pip install yfinance praw sec-edgar-downloader fastapi modal
slowapi psycopg2-binary` first.

Note this deliberately does **not** `pip install -e .`, so the packaging entry
points that register domains with `registry.get()` are inactive. The backtest
CLI imports each domain adapter directly, so it works regardless — but if you
write notebook code that resolves a domain by string id, install the package
properly instead.

## Cell 4 — run a backtest

The event cache is gitignored, so a fresh clone re-pulls seeds from the HN
Algolia API (free, unauthenticated, ~10k req/hr — a 40-story pull is nothing).

```python
%env LIGHTNINGFISH_MODEL=ollama:qwen2.5:7b
%env LIGHTNINGFISH_N_AGENTS=24
%env LIGHTNINGFISH_N_ROUNDS=4
%env LIGHTNINGFISH_LOCAL_TIMEOUT=120
%env PYTHONUNBUFFERED=1

# Submission-only baseline run (also populates the cache hn-early reuses).
!python -m tests.integration.run_backtest hn 40 2>&1 | tee /kaggle/working/hn.log
```

```python
# Early-comments run on those same stories (paired), then the blind subgroup.
!python -m tests.integration.run_backtest hn-early 2>&1 | tee /kaggle/working/hn_early.log
!python -m tests.integration.run_backtest hn-early blind 2>&1 | tee /kaggle/working/hn_blind.log
```

Run `hn` **before** `hn-early`: the early-comments experiment deliberately reads
its story ids from the submission-only cache so the two runs are paired on
identical events.

## Cell 5 — keep the results

```python
!cp -r .cache/lightningfish /kaggle/working/cache
!ls -la /kaggle/working/*.log /kaggle/working/cache
```

Everything under `/kaggle/working` is saved as notebook output and downloadable
after the session ends. Saving the cache means a later session — or your local
machine — can re-score without re-fetching.

---

## Why this is worth doing beyond speed

Sample size is the binding constraint on every claim in
[../METHODOLOGY.md](../METHODOLOGY.md). At n≈22–36 the binomial test against the
best baseline cannot register anything short of a huge margin, so runs at this
scale can support negative conclusions but not positive ones. Cheap GPU time
changes what is answerable: a 300–500 story pull, which is impractical locally,
is a normal Kaggle session and is what a positive result would actually need.

Raise `limit` in the `hn` pull to scale up. The Algolia API is the free part;
simulation time is what grows.
