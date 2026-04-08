# Scenario 5 — Retransmissions (Silent Performance Killer)

## Symptom
No errors. Service is slow. Users complain about latency. Application logs look normal.

## Meaning
TCP retransmits happen when ACKs don't arrive in time. The sender waits, then resends the lost segment. Each retransmit adds latency — and it's completely invisible to the application layer. No errors thrown, just slowness.

High retransmit rate = packet loss somewhere in the network path.

## What Causes It
- Physical network instability or packet loss
- Overloaded NIC dropping packets
- MTU mismatch causing fragmentation and drops
- Congested network path between services
- Misconfigured network equipment

## What We Did

**retransmit-server.py** — serves 100KB of data per connection:
```python
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(5)
print("Listening...")

while True:
    conn, addr = server.accept()
    conn.send(b"X" * 100000)
    conn.close()
```

**Introduced 30% packet loss using `tc netem`:**
```bash
sudo tc qdisc add dev lo root netem loss 30%
```

**Client that receives data and measures time:**
```bash
time python3 -c "
import socket
s = socket.socket()
s.connect(('127.0.0.1', 9999))
data = b''
while True:
    chunk = s.recv(4096)
    if not chunk:
        break
    data += chunk
print(f'Received {len(data)} bytes')
s.close()
"
```

**Cleanup:**
```bash
sudo tc qdisc del dev lo root
```

## What We Observed

| Condition | Time to receive 100KB |
|---|---|
| 30% packet loss (retransmits) | 1.082s |
| No packet loss (clean) | 0.023s |

**~47x slower** — same data, same code, same machine. The only difference was packet loss forcing TCP retransmits. The application received all 100,000 bytes correctly both times — just dramatically slower.

This is why retransmissions are called a silent killer. No error, no alert, just latency.

## How to Detect Retransmissions

```bash
# Global retransmit counter — is it climbing?
netstat -s | grep retransmit

# Per-connection retransmit info
ss -ti

# In Wireshark — filter for retransmissions
tcp.analysis.retransmission

# In tcpdump — look for same sequence number appearing twice
# Same seq + same src/dst ports = retransmit
```

## How to Read Retransmits in tcpdump

tcpdump doesn't label retransmits explicitly. You identify them by:

1. **Same source and destination ports** — same connection
2. **Same sequence number** — identical packet being resent
3. **Timing gap** — appears after a timeout delay

```
10:05:01  127.0.0.1.54321 > 127.0.0.1.9999  seq 1000  ← original
10:05:02  127.0.0.1.54321 > 127.0.0.1.9999  seq 1000  ← retransmit (same seq)
```

Wireshark labels these explicitly as `[TCP Retransmission]` in the Info column.

## Production Debug Flow

```
Users report slowness, no errors
        ↓
Check retransmit counters           → netstat -s | grep retransmit
        ↓
Is the count climbing?              → watch -n 1 'netstat -s | grep retransmit'
        ↓
Which connections are affected?     → ss -ti (shows retrans per connection)
        ↓
Capture traffic                     → tcpdump -i eth0 -w capture.pcap
        ↓
Analyze in Wireshark                → tcp.analysis.retransmission filter
        ↓
Identify the network path           → traceroute, check NIC stats
```

## Simulate and Clean Up

```bash
# Add packet loss
sudo tc qdisc add dev lo root netem loss 30%

# Add latency (alternative simulation)
sudo tc qdisc add dev lo root netem delay 100ms

# Add both
sudo tc qdisc add dev lo root netem delay 100ms loss 10%

# Remove all tc rules
sudo tc qdisc del dev lo root

# Verify cleanup
tc qdisc show dev lo
```

## Key Takeaway
Retransmissions are invisible to the application — no errors, just latency. 30% packet loss caused a 47x slowdown in this lab. Always check `netstat -s | grep retransmit` early in a latency investigation before assuming it's an application problem.
