# Scenario 3 — CLOSE_WAIT Accumulation

## Symptom
Hundreds or thousands of connections stuck in `CLOSE_WAIT`. Service may eventually start refusing new connections.

## Meaning
The remote side closed the connection (sent FIN), your server acknowledged it — but your **application never called `close()` on the socket**. The server is holding the socket open forever waiting for the app to close its side.

This is almost always an **application bug**, not a network bug.

## What Causes It
- Connection pool not releasing connections properly
- Missing error handling — connection leaked on exception
- Resource leak in application code
- App processing requests but never closing the socket after finishing

## What We Did

**buggy-server.py** — accepts connections but intentionally never closes them:
```python
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(5)
print("Listening on port 9999...")

while True:
    conn, addr = server.accept()
    print(f"Connection from {addr}")
    # Intentional bug — conn.close() never called
```

**Terminal 2 — watch connection states live:**
```bash
watch -n 1 'ss -tan | grep 9999'
```

**Terminal 3 — connect then disconnect:**
```bash
telnet 127.0.0.1 9999
# Once connected: Ctrl+] then type: close
```

## What We Observed

After closing telnet:
```
LISTEN     0   5   0.0.0.0:9999    0.0.0.0:*
CLOSE-WAIT 1   0   127.0.0.1:9999  127.0.0.1:48624   ← server stuck
FIN-WAIT-2 0   0   127.0.0.1:48624 127.0.0.1:9999    ← client waiting
```

**CLOSE-WAIT on server (port 9999):**
- Client sent FIN → server ACKed it
- Server app never called `conn.close()`
- Socket stuck open forever

**FIN-WAIT-2 on client (port 48624):**
- Client sent FIN, got ACK back
- Client waiting for server's FIN — which never comes
- Client stuck here until OS timeout

**Gotcha hit during lab:**
Leftover iptables DROP rule from Scenario 2 was still active, causing SYN-SENT to hang. The lesson: always verify cleanup after iptables changes before moving to the next scenario.

## Production Impact at Scale

Each CLOSE_WAIT connection holds a **file descriptor** open. Linux limits file descriptors per process (default `ulimit -n` is often 1024).

```
1000 leaked connections → 1000 file descriptors consumed
Hit ulimit → "Too many open files"
Service stops accepting new connections entirely
```

## Debug Commands

```bash
# How many CLOSE_WAIT connections?
ss -tan | grep CLOSE_WAIT | wc -l

# Which process is responsible?
ss -tanp | grep CLOSE_WAIT

# Is the process hitting fd limits?
cat /proc/<pid>/limits | grep "open files"
ls -l /proc/<pid>/fd | wc -l
```

## The Fix

```python
# Wrong — socket leak
conn, addr = server.accept()
conn.send(b"hello")
# conn.close() forgotten

# Right — explicit close
conn, addr = server.accept()
conn.send(b"hello")
conn.close()

# Better — context manager, closes automatically
with server.accept()[0] as conn:
    conn.send(b"hello")
```

## CLOSE_WAIT vs FIN_WAIT_2

These always appear together as a pair when this bug occurs:

| State | Who | Meaning |
|---|---|---|
| `CLOSE_WAIT` | Server | Remote closed, app hasn't. **The bug is here.** |
| `FIN_WAIT_2` | Client | Sent FIN, got ACK, waiting for remote FIN that never comes |

## Key Takeaway
CLOSE_WAIT = application bug, not network bug. Each leaked connection eats a file descriptor. At scale this kills the service. Debug with `ss -tanp | grep CLOSE_WAIT` to find the offending process, then fix the code to always close sockets.
