# TCP Layer 4/7 — SRE Troubleshooting Runbooks

Hands-on TCP troubleshooting scenarios simulated on Linux. Each scenario covers a real production failure mode — what it looks like, why it happens, how to debug it, and how to fix it.

Built as a personal learning lab while preparing for SRE/Platform Engineering interviews.

---

## Scenarios

| # | Scenario | Key Symptom | Root Cause |
|---|---|---|---|
| 1 | Connection Refused | Immediate error on connect | Nothing listening on the port |
| 2 | Connection Timeout | Hangs forever, no response | Packets dropped silently by firewall |
| 3 | CLOSE_WAIT Accumulation | Connections stuck in CLOSE_WAIT | App bug — socket never closed |
| 4 | TIME_WAIT Exhaustion | New connections fail at scale | Port range exhausted by short-lived connections |
| 5 | Retransmissions | No errors, but very slow | Packet loss forcing TCP retransmits |
| 6 | Port Exhaustion | Outbound connections fail, remote is healthy | Ephemeral port range exhausted |
| 7 | Stale Connections | Requests hang on idle connections | Dead peer not detected — keepalive misconfigured |

---

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

## Quick Reference — Debug Commands

| Command | Purpose |
|---|---|
| `ss -tunaep` | All TCP/UDP connections with state, process, port |
| `ss -tan \| grep <STATE>` | Filter connections by state |
| `ss -tanp \| grep <port>` | Connections on a port with owning process |
| `ss -ti` | Per-connection TCP info including retransmits |
| `netstat -an` | Same as ss, older but widely available |
| `netstat -s \| grep retransmit` | Global retransmit counters |
| `tcpdump -i eth0 port 443` | Capture packets on a specific port |
| `tcpdump -i eth0 port 443 -w out.pcap` | Save capture for Wireshark analysis |
| `telnet <host> <port>` | Quick check if port is reachable |
| `curl -v https://<host>` | Verbose HTTP — shows DNS, TCP, TLS, request, response |
| `iptables -L -n -v` | Check firewall rules |
| `cat /proc/sys/net/ipv4/ip_local_port_range` | Check ephemeral port range |
| `ulimit -n` | Check file descriptor limit for current process |

---

## Connection States Cheat Sheet

| State | Meaning | SRE Relevance |
|---|---|---|
| `SYN_SENT` | Client sent SYN, waiting for SYN-ACK | Normal during connect |
| `ESTABLISHED` | Connection live, data flowing | Healthy state |
| `CLOSE_WAIT` | Remote closed, app hasn't | **Bug — app not closing sockets** |
| `TIME_WAIT` | Post-close 60s waiting period | Normal, problematic at scale |
| `FIN_WAIT_1/2` | Our side initiated close | Normal during teardown |
| `CLOSED` | Fully terminated | Normal |

---

## Environment

- OS: Ubuntu Linux
- Tools: `ss`, `tcpdump`, `wireshark`, `tshark`, `iptables`, `tc`, `netstat`, `telnet`, `curl`, `nc`
- Simulations written in Python 3

---

## Packet Capture Workflow

`tcpdump` filters by IP/port, not process name. Find the port first:

```bash
# Find your app's port
ss -tunaep | grep <process_name>

# Capture on that port
sudo tcpdump -i eth0 port 8080 -w capture.pcap

# Analyze in Wireshark
wireshark capture.pcap
```

**Useful Wireshark filters:**
```
tcp.port == 8080                  # filter by port
tcp.flags.syn == 1                # SYN packets only — see the handshake
tcp.analysis.retransmission       # retransmitted packets
tcp.flags.reset == 1              # RST packets — forceful resets
```
