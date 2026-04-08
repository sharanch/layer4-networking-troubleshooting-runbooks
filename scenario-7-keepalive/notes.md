# Scenario 7 — Stale Connections (TCP Keepalive)

## Symptom
Long-lived connections (DB connections, persistent API connections) appear `ESTABLISHED` in `ss` output but requests hang indefinitely. The remote service is actually gone — rebooted, network partition, crashed — but your side doesn't know yet.

## Meaning
TCP has no built-in mechanism to detect a dead peer on an idle connection. If no data flows, the connection looks `ESTABLISHED` forever — even if the remote host is gone. TCP Keepalive solves this by sending small probe packets on idle connections to verify the peer is still alive.

Default keepalive timeout on Linux: **7200 seconds (2 hours)** — far too long for production.

## What Causes Stale Connections
- Remote host rebooted or crashed
- Network partition between client and server
- Firewall or NAT timeout silently dropping the idle connection
- Cloud provider NLB/NAT idle timeout (often 350s on AWS)

## What We Did

**Simulate a large file download — then kill the server mid-transfer:**

Terminal 1 — create a large file and serve it:
```bash
dd if=/dev/zero of=largefile.bin bs=1M count=100
python3 -m http.server 9999
```

Terminal 2 — client downloading slowly:
```bash
curl http://localhost:9999/largefile.bin --limit-rate 10k -o /dev/null
```

Kill the server mid-transfer and observe the client hanging with an `ESTABLISHED` connection that leads nowhere.

## TCP Keepalive Settings

```bash
# How long to wait before sending first probe on an idle connection
sysctl net.ipv4.tcp_keepalive_time     # default: 7200s (2 hours)

# Interval between probes
sysctl net.ipv4.tcp_keepalive_intvl    # default: 75s

# How many probes before giving up and declaring the connection dead
sysctl net.ipv4.tcp_keepalive_probes   # default: 9
```

With defaults: keepalive kicks in after **2 hours** of idle. Then sends 9 probes, 75s apart. Total time to detect a dead connection: up to **2 hours + 11 minutes**.

In production this is unacceptable — a DB connection pool could hold dead connections for hours.

## Tuning Keepalive

```bash
# More aggressive — detect dead connections within ~30 seconds
sudo sysctl -w net.ipv4.tcp_keepalive_time=10
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=5
sudo sysctl -w net.ipv4.tcp_keepalive_probes=3
# 10s idle → 3 probes × 5s apart = dead detected in ~25s
```

Make permanent in `/etc/sysctl.conf`:
```
net.ipv4.tcp_keepalive_time = 10
net.ipv4.tcp_keepalive_intvl = 5
net.ipv4.tcp_keepalive_probes = 3
```

## Application-Level Keepalive

OS-level keepalive applies to all connections. For targeted control, enable it per-socket in your application:

```python
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 9999))

# Enable keepalive on this socket
s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

# Set per-socket keepalive parameters (Linux only)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)   # idle time before first probe
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)   # interval between probes
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)     # number of probes
```

Most database clients and HTTP libraries have keepalive settings in their connection pool config — prefer those over OS-level tuning for application connections.

## Production Debug Flow

```
Requests hanging on what looks like an ESTABLISHED connection
        ↓
Check connection state              → ss -tan | grep ESTABLISHED
        ↓
Is the remote actually reachable?   → ping <remote_ip>
        ↓
Can you open a NEW connection?      → telnet <remote_ip> <port>
        ↓
Check keepalive settings            → sysctl net.ipv4.tcp_keepalive_time
        ↓
Is there a NAT/firewall timeout?    → check cloud provider idle timeout settings
```

## Cloud Provider NAT Timeouts — Important SRE Note

Cloud NAT and load balancers have their own idle timeouts that can silently kill connections before TCP keepalive even fires:

| Provider | Default idle timeout |
|---|---|
| AWS NLB | 350 seconds |
| AWS ALB | 60 seconds |
| GCP Cloud NAT | 30 seconds (UDP), 1200s (TCP established) |
| Azure Load Balancer | 4 minutes |

If your keepalive interval is longer than the NAT idle timeout, the NAT drops the connection silently before keepalive probes can detect it. Always tune keepalive to be **shorter than** any NAT/LB idle timeout in your path.

## Key Takeaway
Stale connections appear ESTABLISHED but lead nowhere. Default Linux keepalive (2 hours) is too slow for production. Tune keepalive aggressively or enable it at the application level. Always account for NAT/LB idle timeouts — they can kill connections before keepalive fires.
