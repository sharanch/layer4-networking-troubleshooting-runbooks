# Scenario 2 — Connection Timeout

## Symptom
Connection attempt just hangs — no response, no error, no refusal. Just silence until timeout.

## Meaning
Packets are being dropped silently. The SYN leaves the client but SYN-ACK never comes back. Unlike connection refused (where the OS sends a RST back immediately), a timeout means something in the path is discarding packets without telling anyone.

## Key Distinction

> **Refused** = something is there but rejecting you. Instant response.
> **Timeout** = packets are disappearing. Hangs forever.

## What Causes It
- Firewall with DROP rule (silently discards packets)
- Cloud security group blocking the port
- Wrong IP or routing — packets going nowhere
- Service not reachable from this network path

## What We Did

**Terminal 1 — watch the wire:**
```bash
sudo tcpdump -i lo port 9999 -n
```

**Terminal 2 — add a DROP rule to simulate a firewall:**
```bash
sudo iptables -A INPUT -p tcp --dport 9999 -j DROP
```

**Terminal 3 — try to connect:**
```bash
telnet localhost 9999
```

**Cleanup:**
```bash
sudo iptables -D INPUT -p tcp --dport 9999 -j DROP
```

## What We Observed

tcpdump output:
```
09:12:07  IP 127.0.0.1.54924 > 127.0.0.1.9999: Flags [S], seq 1345400187
09:12:16  IP 127.0.0.1.54924 > 127.0.0.1.9999: Flags [S], seq 1345400187
09:12:32  IP 127.0.0.1.54924 > 127.0.0.1.9999: Flags [S], seq 1345400187
```

**How to read retransmits:**
- `Flags [S]` = SYN packet — connection attempt
- **Same sequence number** every time = same packet being retransmitted, not a new attempt
- **Timing gaps double** — 8s → 16s → 32s — TCP exponential backoff
- **No SYN-ACK ever appears** — packets being dropped

**Gotcha hit during lab:**
After cleanup, the next scenario still failed with SYN-SENT. Root cause: iptables DROP rule was still active. Always verify cleanup:
```bash
sudo iptables -L INPUT -n -v
```

## DROP vs REJECT

| Rule | Behavior | Client sees |
|---|---|---|
| `DROP` | Packet silently discarded | Connection timeout — hangs |
| `REJECT` | Packet discarded + RST sent back | Connection refused — immediate error |

Real firewalls and cloud security groups use DROP — that's why timeouts are harder to debug than refused connections. There's no feedback.

## Production Debug Flow

```
Got connection timeout (hangs)
        ↓
Can we reach the host at all?    → ping <host>
        ↓
Is the SYN leaving our machine?  → tcpdump -i eth0 host <target> and port <port>
        ↓
Is a firewall dropping packets?  → iptables -L -n -v
        ↓
Is the route correct?            → traceroute <host>
        ↓
Is the security group correct?   → check cloud console
```

## Key Takeaway
Timeout = packets disappearing. tcpdump on the client shows SYN retransmits with exponential backoff and no SYN-ACK. The fix is always upstream — firewall rule, security group, or routing — not the application.
