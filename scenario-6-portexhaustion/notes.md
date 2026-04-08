# Scenario 6 — Port Exhaustion on Outbound Connections

## What is this?

Every time your application opens a TCP connection to another service (a database, an API, a microservice), the OS needs to assign a **source port** on your machine for that connection. This source port comes from a finite pool called the **ephemeral port range**.

On Linux, this range is typically `32768–60999` — about **28,231 ports**.

When you open and close connections faster than the OS can recycle them, you burn through this pool. Eventually there are no free ports left. New connections fail. Your service crashes or becomes unavailable — even though the remote service is perfectly healthy.

This is **port exhaustion**.

---

## The Root Cause

Each TCP connection is identified by a unique 4-tuple:

```
(source IP, source port, destination IP, destination port)
```

The destination IP and port are fixed (e.g., your DB at `10.0.0.5:5432`). The source IP is your machine. The only variable is the **source port** — and the OS picks one from the ephemeral range for each new connection.

When a connection closes, it enters `TIME_WAIT` state for **60 seconds**. During this window, the source port is NOT available for reuse. This exists to ensure stale packets from the old connection don't corrupt a new one.

```
Open connection  → ephemeral port assigned (e.g., 54231)
Close connection → port enters TIME_WAIT for 60s
                 → port is LOCKED for 60 seconds
New connection   → OS picks next available port
...repeat 28,231 times...
No ports left    → EADDRNOTAVAIL → connection fails
```

If you're opening thousands of short-lived connections per second, the ports pile up in `TIME_WAIT` faster than they expire. You hit the ceiling.

---

## What We Observed in the Lab

### Environment
- Linux VM (Ubuntu)
- Ephemeral port range: `32768–60999` = **28,231 ports**
- Python TCP server on `localhost:9999`
- Client opening 1 new connection per request (no pooling)

### What happened

**Without server delay (`time.sleep`):**

The client made 80,000+ connections without failing. `ss -tan | grep TIME_WAIT` showed **0** at all times. The kernel was recycling ports faster than `ss` could observe them — loopback (`127.0.0.1`) is so fast that the full TCP lifecycle completes in microseconds.

```
Connections made: 83,000+
TIME_WAIT visible: 0
Reason: loopback too fast — states transitioned before ss could catch them
```

**With server delay (`time.sleep(0.1)`):**

The server held each connection open for 100ms. Now TIME_WAIT connections accumulated visibly.

```
23328  TIME_WAIT    ← ports consumed, waiting to expire
   56  CLOSE_WAIT   ← server hasn't closed some sockets
   34  FIN_WAIT-2   ← client waiting for server's FIN
   24  FIN_WAIT-1   ← client sent FIN, waiting for ACK
    1  LISTEN       ← server socket
```

The client eventually failed at exactly:

```
FAILED at 28231: [Errno 99] Cannot assign requested address
```

**28,231 — exactly the ephemeral port range.** Not one more.

---

## Two Ceilings You Can Hit

Port exhaustion is one ceiling. But we also hit a second one during the lab:

```
Ceiling 1 — File Descriptors (ulimit -n)
  Default limit: 1024 open files per process
  Every socket = 1 file descriptor
  Server with 1024+ concurrent connections → OSError: Too many open files
  Fix: ulimit -n 65535

Ceiling 2 — Ephemeral Ports (ip_local_port_range)
  Default range: ~28,231 ports
  Client opening 1 connection per request → EADDRNOTAVAIL at 28,231
  Fix: connection pooling (not widening the range)
```

In production, you can hit either. The file descriptor limit kills your **server**. The port limit kills your **client** (or any service making outbound calls).

---

## How to Diagnose in Production

### Check your ephemeral port range
```bash
cat /proc/sys/net/ipv4/ip_local_port_range
# 32768   60999
```

### Count TIME_WAIT connections
```bash
ss -tan | grep TIME_WAIT | wc -l
```

### See a breakdown of all connection states
```bash
ss -tan | grep 9999 | awk '{print $1}' | sort | uniq -c | sort -rn
```

### Count outbound connections to a specific destination
```bash
ss -tan | grep ESTABLISHED | grep <remote_ip> | wc -l
```

### Check if port reuse is enabled
```bash
sysctl net.ipv4.tcp_tw_reuse
# 0 = disabled, 1 = enabled
```

### Check your file descriptor limit
```bash
ulimit -n
```

---

## Connection State Cheat Sheet (relevant to this scenario)

| State | What it means |
|---|---|
| `ESTABLISHED` | Connection is live and healthy |
| `TIME_WAIT` | Connection closed, port locked for 60s |
| `CLOSE_WAIT` | Remote closed, your app hasn't called `close()` yet |
| `FIN_WAIT-1` | Your side sent FIN, waiting for ACK |
| `FIN_WAIT-2` | Got ACK for your FIN, waiting for remote's FIN |

In a port exhaustion scenario, **TIME_WAIT is the killer**. Each entry represents a locked port.

---

## The Fix

### Wrong fix — widen the port range
```bash
# This just delays the problem
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
```
More ports means you can open more connections before failing. But if you're opening 1 connection per request at scale, you'll still exhaust a larger range eventually. This is a band-aid.

### Wrong fix — enable tcp_tw_reuse
```bash
# Allows reuse of TIME_WAIT sockets in some cases
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
```
This helps at the margin but doesn't fix the root cause. It also only applies to outbound connections where timestamps are enabled.

### Right fix — connection pooling

Stop opening a new connection per request. Open a pool of connections at startup, reuse them across requests.

```
Without pooling:
  Request 1 → open connection → use → close → TIME_WAIT
  Request 2 → open connection → use → close → TIME_WAIT
  Request N → open connection → EADDRNOTAVAIL

With pooling:
  Startup → open 10 connections → keep them open
  Request 1 → borrow connection from pool → use → return
  Request 2 → borrow connection from pool → use → return
  Request N → borrow connection from pool → use → return
  TIME_WAIT: 0
  Ports used: 10 (forever)
```

### Right fix — HTTP Keep-Alive

For HTTP services, enable keep-alive. This reuses the underlying TCP connection across multiple HTTP requests without closing and reopening it.

```python
# Bad — new TCP connection per HTTP request
import urllib.request
for i in range(10000):
    urllib.request.urlopen('http://api.example.com/data')

# Good — reuse TCP connection via session
import requests
session = requests.Session()   # keep-alive enabled by default
for i in range(10000):
    session.get('http://api.example.com/data')
```

---

## Real-World Impact

This pattern shows up constantly in production:

- **Microservices** making HTTP calls to other services without keep-alive
- **Database clients** opening a new connection per query instead of using a pool
- **Lambda/serverless functions** that can't maintain persistent connections (architectural constraint)
- **Scrapers or batch jobs** hitting external APIs in a tight loop

The symptom is always the same: the service making outbound calls starts throwing connection errors, while the **remote service looks completely healthy**. This makes it easy to misdiagnose as a remote-side problem.

---

## Quick Reference

```bash
# See TIME_WAIT count
ss -tan | grep TIME_WAIT | wc -l

# See all states breakdown
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn

# Check ephemeral range
cat /proc/sys/net/ipv4/ip_local_port_range

# Check fd limit
ulimit -n

# Raise fd limit for current session
ulimit -n 65535

# Check tw_reuse
sysctl net.ipv4.tcp_tw_reuse
```

---

## Key Takeaways

1. **Every outbound TCP connection consumes an ephemeral port** for up to 60 seconds after closing (TIME_WAIT).
2. **The ephemeral range on Linux is ~28,231 ports** by default. Exhaust it and new connections fail with `EADDRNOTAVAIL`.
3. **Widening the range is a band-aid.** The real fix is connection pooling or keep-alive.
4. **Loopback (127.0.0.1) masks the problem** — connections cycle too fast to observe TIME_WAIT. Real behavior shows on actual network interfaces.
5. **File descriptor exhaustion is a separate but related ceiling** — your server hits `EMFILE` if it holds too many concurrent sockets open without raising `ulimit -n`.
6. **The remote service looks healthy** during port exhaustion — this is a client-side resource problem, not a remote-side problem.
