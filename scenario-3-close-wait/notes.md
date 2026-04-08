Here's the roundup:

---

**What we simulated:**
- A buggy Python server that accepts connections but never calls `conn.close()`

**What we used:**
- `buggy_server.py` — the intentionally broken server
- `watch -n 1 'ss -tan | grep 9999'` — live connection state monitor
- `telnet 127.0.0.1 9999` — client that connects then disconnects

**What we observed:**
- Client closed with `Ctrl+] → close`
- Server side stuck in `CLOSE-WAIT` — remote closed, app never closed its socket
- Client side stuck in `FIN-WAIT-2` — waiting for server FIN that never comes

**The gotcha we hit:**
- Leftover iptables DROP rule from Scenario 2 was silently breaking things — good real world lesson, always verify cleanup

**Key takeaways:**
- CLOSE_WAIT = application bug, not a network bug
- Each leaked connection holds a file descriptor
- At scale this exhausts file descriptors → `too many open files` → service stops accepting connections
- Debug with `ss -tanp | grep CLOSE_WAIT` to find the offending process

---


