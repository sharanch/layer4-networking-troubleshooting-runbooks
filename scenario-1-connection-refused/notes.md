# Scenario 1 — Connection Refused

## Symptom
Client immediately gets an error when trying to connect. No hang, no wait — instant rejection.

```
telnet: Unable to connect to remote host: Connection refused
curl: (7) Failed to connect to host port 443: Connection refused
```

## Meaning
The port isn't open, or nothing is listening on it. Unlike a timeout (where packets disappear silently), a refused connection means the OS received the SYN and actively sent back a **TCP RST** — "nothing here, go away."

## Key Distinction

> **Refused** = OS got your SYN and rejected it. Instant response.
> **Timeout** = packets are disappearing. Hangs forever.

## What Causes It
- Service crashed or never started
- Service is listening on a different port than expected
- Firewall using REJECT (sends RST) rather than DROP (silent)
- Binding to wrong interface — e.g. listening on `127.0.0.1` but connecting from external IP

## Debug

```bash
# Is anything listening on this port?
ss -tunaep | grep 443

# Quick reachability test
telnet <host> 443
curl -v https://<host>

# If you have access to the server — what is the process?
ss -tanp | grep 443

# Check firewall rules — REJECT vs DROP
iptables -L -n -v

# Check what interface the service is bound to
ss -tunaep | grep <process_name>
```

## What You'd See in tcpdump

With DROP (timeout):
```
SYN → (silence)
SYN → (silence, retransmit)
SYN → (silence, retransmit)
```

With REJECT (refused):
```
SYN → RST-ACK   ← instant rejection, no retransmits
```

The presence of RST in tcpdump is the signature of connection refused.

## Production Debug Flow

```
Got "connection refused"
        ↓
Is the service running?          → ps aux | grep <service>
        ↓
Is it listening on the right port?  → ss -tunaep | grep <port>
        ↓
Is it bound to the right interface? → ss -tunaep | grep <process>
        ↓
Is a firewall REJECT rule active?   → iptables -L -n -v
```

## Key Takeaway
Connection refused is easier to debug than timeout — the OS is telling you clearly that nothing is there. The hardest part is figuring out *why* the service isn't listening: crashed, wrong port, wrong interface, or firewall REJECT.
