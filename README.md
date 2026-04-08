# layer4-networking-troubleshooting-runbooks

# TCP Layer 4 — SRE Troubleshooting Scenarios

## The Mental Model

When a TCP issue lands on you, work up the stack systematically:

```
Can we reach the host at all?        → ping, traceroute
        ↓
Is the port open?                    → telnet, ss on server
        ↓
Are packets arriving?                → tcpdump on server
        ↓
Is the app accepting connections?    → ss -tunaep, app logs
        ↓
Is the connection staying healthy?   → retransmits, keepalive, connection state
```

---

## Scenario 1 — Connection Refused

	**Symptom:** Client immediately gets an error when trying to connect.
	
	**Meaning:** The port isn't open, or nothing is listening.
	
	**Debug:**
	```bash
	# Check if the service is actually listening
	ss -tunaep | grep 443
	
	# Quick reachability test from another machine
	telnet <host> 443
	curl -v https://<host>
	```
	
	**Common causes:**
	- Service crashed
	- Wrong port configured
	- Firewall blocking

---

## Scenario 2 — Connection Timeout

**Symptom:** Connection attempt just hangs — no response, no refusal.

**Meaning:** Packets are being dropped silently. The SYN leaves the client but SYN-ACK never returns.

**Key distinction:**
> **Refused** = something is there but rejecting you.
> **Timeout** = packets are disappearing.

**Debug:**
```bash
# Check if SYN is leaving your machine
tcpdump -i eth0 host <target> and port 443

# Check if firewall is dropping packets
iptables -L -n -v
```

**Common causes:**
- Firewall dropping packets silently
- Security group misconfigured
- Wrong IP or routing issue

---

## Scenario 3 — CLOSE_WAIT Accumulation

**Symptom:** Hundreds or thousands of connections stuck in `CLOSE_WAIT`.

**Meaning:** The remote side closed the connection (sent FIN), your server acknowledged it, but your **application never called `close()` on the socket**. This is almost always an application-level bug.

**Debug:**
```bash
# Count CLOSE_WAIT connections
ss -tan | grep CLOSE_WAIT | wc -l
```

**Impact if left unchecked:** Exhausts file descriptors → service starts refusing new connections entirely.

**Common causes:**
- Connection pool not releasing connections
- Missing error handling in application code
- Resource leak

---

## Scenario 4 — TIME_WAIT Exhaustion

**Symptom:** Thousands of `TIME_WAIT` connections on a high-traffic service. New outbound connections start failing.

**Meaning:** `TIME_WAIT` is normal — it's a 60-second waiting period after a connection closes to ensure no stale packets arrive. But at scale, opening and closing thousands of short-lived connections per second exhausts the ephemeral port range (`32768–60999` on Linux, ~28,000 ports).

**Debug:**
```bash
# Count TIME_WAIT connections
ss -tan | grep TIME_WAIT | wc -l

# Check ephemeral port range
cat /proc/sys/net/ipv4/ip_local_port_range
```

**Fix:**
```bash
# Allow reuse of TIME_WAIT sockets safely
sysctl net.ipv4.tcp_tw_reuse=1
```

---

## Scenario 5 — Retransmissions (Silent Performance Killer)

**Symptom:** No errors, but the service is slow. Users complain of latency.

**Meaning:** TCP retransmits happen when ACKs don't arrive in time. Each retransmit adds latency. High retransmit rate = network instability or packet loss somewhere in the path.

**Debug:**
```bash
# Check retransmit counters
netstat -s | grep retransmit

# Per-connection retransmit stats
ss -ti
```

**Common causes:**
- Bad network path
- Overloaded NIC
- MTU mismatch

---

## Scenario 6 — Port Exhaustion on Outbound Connections

**Symptom:** Your service makes outbound calls (to DB, API, microservice). New connections start failing even though the remote service is healthy.

**Meaning:** You've run out of ephemeral ports on your side for outbound connections.

**Debug:**
```bash
# Check ephemeral port range
cat /proc/sys/net/ipv4/ip_local_port_range

# Count outbound connections to a specific destination
ss -tan | grep ESTABLISHED | grep <remote_ip> | wc -l
```

**Fix:** Widen the port range, but more importantly fix the root cause — implement connection pooling, enable keep-alive, stop opening a new connection per request.

---

## Scenario 7 — Stale Connections (TCP Keepalive)

**Symptom:** Long-lived connections (DB connections, persistent API connections) appear `ESTABLISHED` but the remote is actually gone — rebooted, network partition, etc. Requests hang indefinitely.

**Meaning:** TCP keepalive sends small probe packets on idle connections to detect dead peers. Default keepalive timeout is 2 hours — far too long for most production services.

**Check and tune:**
```bash
sysctl net.ipv4.tcp_keepalive_time    # default 7200s (2 hours)
sysctl net.ipv4.tcp_keepalive_intvl   # interval between probes
sysctl net.ipv4.tcp_keepalive_probes  # how many probes before giving up
```

**Fix:** Tune keepalive at OS level, or enable it at the application/connection pool level for faster dead connection detection.

---

## Quick Reference — Debug Commands

| Command | Purpose |
|---|---|
| `ss -tunaep` | Show all TCP/UDP connections with state, process, port |
| `ss -tan \| grep <STATE>` | Filter connections by state |
| `ss -ti` | Per-connection TCP info including retransmits |
| `netstat -an` | Same as ss, older but widely available |
| `netstat -s \| grep retransmit` | Global retransmit counters |
| `tcpdump -i eth0 port 443` | Capture packets on a specific port |
| `tcpdump -i eth0 port 443 -w out.pcap` | Save capture for Wireshark analysis |
| `telnet <host> <port>` | Quick check if port is reachable |
| `curl -v https://<host>` | Verbose HTTP — shows full request/response + TLS |
| `iptables -L -n -v` | Check firewall rules |

---

## Packet Capture for Specific Applications

`tcpdump` filters by IP/port, not process name. Workflow:

```bash
# Step 1 — find your app's port
ss -tunaep | grep <process_name>

# Step 2 — capture on that port
tcpdump -i eth0 port 8080 -w capture.pcap

# Step 3 — open in Wireshark
wireshark capture.pcap
```

**Useful Wireshark filters:**
```
tcp.port == 8080         # filter by port
tcp.flags.syn == 1       # show only SYN packets — see the handshake
tcp.analysis.retransmission  # show retransmissions
tcp.flags.reset == 1     # show RST packets — forceful resets
```

**What to look for in a capture:**
- **RST packets** — connection forcefully reset
- **Retransmissions** — packets being resent, indicating loss
- **SYN without SYN-ACK** — connection never established
- **TLS alerts** — handshake failing (leads into Layer 7 / PKI)

---

## Connection States Cheat Sheet

| State | Meaning | SRE Relevance |
|---|---|---|
| `SYN_SENT` | Client sent SYN, waiting for SYN-ACK | Normal during connect |
| `ESTABLISHED` | Connection live, data flowing | Healthy state |
| `CLOSE_WAIT` | Remote closed, app hasn't | **Bug — app not closing sockets** |
| `TIME_WAIT` | Post-close waiting period | Normal, problematic at scale |
| `FIN_WAIT_1/2` | Our side initiated close | Normal during teardown |
| `CLOSED` | Fully terminated | Normal |
