# Scenario 4 — TIME_WAIT Exhaustion

## What is TIME_WAIT?
After a TCP connection closes, it enters TIME_WAIT for 60 seconds. This is normal — it ensures no stale packets from the old connection arrive and confuse a new one on the same port.

## The Problem at Scale
Every closed connection consumes an ephemeral port for 60 seconds. If you open and close connections faster than they expire, you exhaust the port range and new connections fail.

```
Ephemeral port range on Linux: 32768–60999 (~28,000 ports)
Open/close 28,000 connections → all ports in TIME_WAIT → next connection fails
```

## Error You'd See in Production
```
Cannot assign requested address   (EADDRNOTAVAIL)
```

## What We Did

**time-wait-server.py** — accepts connection, sends response, closes immediately:
```python
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(100)
print("Listening on port 9999...")

while True:
    conn, addr = server.accept()
    conn.send(b"hello\n")
    conn.close()
```

**hammer-client.py** — opens and closes 2000 connections rapidly:
```python
import socket

count = 0
while count < 2000:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 9999))
        s.recv(1024)
        s.close()
        count += 1
    except Exception as e:
        print(f"Error: {e}")

print("Done")
```

## Commands Used

```bash
# Watch TIME_WAIT count live
watch -n 1 'ss -tan | grep TIME-WAIT | wc -l'

# Check ephemeral port range
cat /proc/sys/net/ipv4/ip_local_port_range

# Enable TIME_WAIT reuse (band-aid fix)
sudo sysctl net.ipv4.tcp_tw_reuse=1

# Revert
sudo sysctl net.ipv4.tcp_tw_reuse=0
```

## What We Observed

- 2000 rapid connections generated **~3989 TIME_WAIT entries**
- Roughly 2x connections because loopback counts both client and server sides
- `tcp_tw_reuse=1` didn't help on loopback — count actually went higher to ~7247
- `tcp_tw_reuse` works better in real production where client and server are on different machines

## The Real Fix

`tcp_tw_reuse` is a band-aid. Real fixes:

**Connection pooling** — reuse existing connections, don't open/close per request:
```
Without pooling:
  Request 1 → open → use → close → TIME_WAIT (port locked 60s)
  Request 2 → open → use → close → TIME_WAIT (port locked 60s)
  Request N → open → EADDRNOTAVAIL (ports exhausted)

With pooling:
  Startup → open 10 connections
  Request 1 → borrow → use → return to pool
  Request N → borrow → use → return to pool
  TIME_WAIT: 0
```

**HTTP Keep-Alive** — reuse TCP connections across multiple HTTP requests without closing.

## Key Distinction from CLOSE_WAIT

| | CLOSE_WAIT | TIME_WAIT |
|---|---|---|
| Cause | App bug — socket never closed | Normal — post-close cooldown |
| Fix | Fix the application code | Connection pooling, keep-alive |
| Resource hit | File descriptor exhaustion | Ephemeral port exhaustion |
| Error | `too many open files` | `cannot assign requested address` |

## Key Takeaway
TIME_WAIT is normal but accumulates at scale. 2000 rapid connections generated ~4000 TIME_WAIT entries in this lab. At production traffic rates, ~28,000 ports exhaust quickly. The fix is connection pooling — not kernel tuning.
