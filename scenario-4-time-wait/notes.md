# Scenario 4 — TIME_WAIT Exhaustion

## What is TIME_WAIT?
After a TCP connection closes, it enters TIME_WAIT for 60 seconds.
This is normal — it ensures no stale packets from the old connection
arrive and confuse a new one on the same port.

## The Problem at Scale
Every closed connection consumes an ephemeral port for 60 seconds.
Ephemeral port range on Linux: 32768–60999 (~28,000 ports)
If you open and close connections faster than they expire,
you exhaust the port range → new connections fail.

## Error you'd see in production
Cannot assign requested address

## What we did
- Created time_wait_server.py — accepts connection, sends "hello", closes immediately
- Created hammer-client.py — opens and closes 2000 connections rapidly
- Watched TIME_WAIT count climb to ~3989 (roughly 2x connections, both sides counted)

## Commands used
# Watch TIME_WAIT count live
watch -n 1 'ss -tan | grep TIME-WAIT | wc -l'

# Check ephemeral port range
cat /proc/sys/net/ipv4/ip_local_port_range

# Enable TIME_WAIT reuse (band-aid fix)
sudo sysctl net.ipv4.tcp_tw_reuse=1

# Revert
sudo sysctl net.ipv4.tcp_tw_reuse=0

## What we observed
- 2000 rapid connections generated ~3989 TIME_WAIT entries
- tcp_tw_reuse didn't help much on loopback since both sides
  are on the same machine — count actually went higher to ~7247
- tcp_tw_reuse works better in real production (client and server
  on different machines)

## The Real Fix
tcp_tw_reuse is a band-aid. Real fixes:
- Connection pooling — reuse existing connections, don't open/close per request
- Keep-alive — don't close connections after every request
- These reduce the connection churn that causes TIME_WAIT accumulation

## Key distinction from CLOSE_WAIT
| | CLOSE_WAIT | TIME_WAIT |
|---|---|---|
| Cause | App bug — socket never closed | Normal — post-close cooldown |
| Fix | Fix the application code | Connection pooling, keep-alive |
| Risk | File descriptor exhaustion | Ephemeral port exhaustion |
| Error | too many open files | cannot assign requested address |
