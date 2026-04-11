# curl Cheatsheet — SRE/DevOps Reference

> Organized for real-world debugging: DNS → TCP → TLS → HTTP → scripting

---

## 1. Request Timing Breakdown

The most useful one-liner for understanding full-stack latency:

```bash
curl -o /dev/null -s -w "
DNS lookup:        %{time_namelookup}s
TCP connect:       %{time_connect}s
TLS handshake:     %{time_appconnect}s
TTFB:              %{time_starttransfer}s
Total:             %{time_total}s
HTTP status:       %{http_code}
Downloaded:        %{size_download} bytes
" https://example.com
```

**What each field tells you:**
| Field | Meaning | High value = suspect |
|---|---|---|
| `time_namelookup` | DNS resolution time | Slow DNS resolver |
| `time_connect` | TCP handshake complete | Network latency / firewall |
| `time_appconnect` | TLS handshake complete | Cert chain issues, crypto overhead |
| `time_starttransfer` | Time to first byte (TTFB) | Slow backend / DB query |
| `time_total` | Full request including body | Large response / slow transfer |

Save as a script for repeated use:

```bash
# ~/.local/bin/curl-time
#!/usr/bin/env bash
curl -o /dev/null -s -w "\
DNS:   %{time_namelookup}s\n\
TCP:   %{time_connect}s\n\
TLS:   %{time_appconnect}s\n\
TTFB:  %{time_starttransfer}s\n\
Total: %{time_total}s\n\
HTTP:  %{http_code}\n" "$@"
```

```bash
chmod +x ~/.local/bin/curl-time
curl-time https://api.example.com/health
```

---

## 2. Verbose Output & Header Inspection

```bash
# Full verbose — TLS handshake, request headers, response headers
curl -v https://example.com

# Just response headers (no body)
curl -sI https://example.com

# Request headers only (silent body)
curl -vs https://example.com 2>&1 | grep "^>"

# Response headers only (from verbose)
curl -vs https://example.com 2>&1 | grep "^<"

# See TLS version and cipher negotiated
curl -v https://example.com 2>&1 | grep -E "TLSv|cipher|SSL|certificate"
```

---

## 3. TLS / Certificate Debugging

```bash
# Check TLS version and cipher in use
curl -v https://example.com 2>&1 | grep -E "TLS|SSL|cipher"

# Force specific TLS version
curl --tls-max 1.2 https://example.com
curl --tlsv1.3 https://example.com

# Skip certificate verification (dev only — never prod)
curl -k https://self-signed.internal

# Use a custom CA bundle (internal PKI)
curl --cacert /etc/ssl/internal-ca.crt https://internal.example.com

# Use a client certificate (mTLS)
curl --cert client.crt --key client.key https://mtls.example.com

# Show the server's certificate details
curl -vI https://example.com 2>&1 | grep -A 20 "Server certificate"

# Check cert expiry (combine with openssl)
echo | openssl s_client -connect example.com:443 2>/dev/null \
  | openssl x509 -noout -dates
```

---

## 4. HTTP Methods & Request Body

```bash
# GET (default)
curl https://api.example.com/users

# POST with JSON body
curl -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -d '{"name": "sharan", "role": "sre"}'

# POST from file
curl -X POST https://api.example.com/data \
  -H "Content-Type: application/json" \
  -d @payload.json

# PUT
curl -X PUT https://api.example.com/users/42 \
  -H "Content-Type: application/json" \
  -d '{"name": "updated"}'

# PATCH
curl -X PATCH https://api.example.com/users/42 \
  -d '{"role": "senior-sre"}'

# DELETE
curl -X DELETE https://api.example.com/users/42

# Form data (application/x-www-form-urlencoded)
curl -X POST https://example.com/login \
  -d "username=sharan&password=secret"

# Multipart form (file upload)
curl -X POST https://api.example.com/upload \
  -F "file=@/path/to/file.log" \
  -F "description=incident log"
```

---

## 5. Headers & Authentication

```bash
# Add custom headers
curl -H "X-Request-ID: abc-123" \
     -H "X-Correlation-ID: xyz-456" \
     https://api.example.com

# Bearer token auth
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/me

# Basic auth
curl -u username:password https://api.example.com
# or
curl -H "Authorization: Basic $(echo -n user:pass | base64)" https://api.example.com

# API key in header
curl -H "X-API-Key: $API_KEY" https://api.example.com

# Send a cookie
curl -H "Cookie: session=abc123" https://example.com
# or
curl -b "session=abc123" https://example.com

# Save and reuse cookies
curl -c cookies.txt https://example.com/login -d "user=x&pass=y"
curl -b cookies.txt https://example.com/dashboard
```

---

## 6. Redirects & Following

```bash
# Follow redirects (HTTP -> HTTPS, 301s, 302s)
curl -L https://example.com

# Follow redirects but show each hop
curl -Lv https://example.com 2>&1 | grep -E "Location|HTTP/"

# Limit redirect hops
curl -L --max-redirs 3 https://example.com

# Don't follow — see the redirect response
curl -I https://http-redirect.example.com
```

---

## 7. Timeouts & Retries (Critical in Scripts)

Always set timeouts — never let curl hang in automation.

```bash
# Connect timeout + total max time
curl --connect-timeout 5 --max-time 30 https://api.example.com/health

# Retry on failure (transient errors)
curl --retry 3 --retry-delay 2 https://api.example.com

# Retry including connection refused (useful for service startup)
curl --retry 5 --retry-delay 3 --retry-connrefused https://api.example.com/health

# Retry with exponential backoff
curl --retry 5 --retry-delay 1 --retry-max-time 60 https://api.example.com
```

---

## 8. DNS & Network Debugging

```bash
# Hit a specific IP, send correct Host header (bypass DNS / test specific pod)
curl -H "Host: api.example.com" https://10.0.1.42/health

# Override DNS resolution (resolve hostname to specific IP)
curl --resolve api.example.com:443:10.0.1.42 https://api.example.com/health

# Use a specific DNS server
curl --dns-servers 8.8.8.8 https://example.com

# Test IPv4 vs IPv6 explicitly
curl -4 https://example.com
curl -6 https://example.com

# Check what IP curl resolved to
curl -v https://example.com 2>&1 | grep "Connected to"
```

---

## 9. Output & Response Handling

```bash
# Silent (no progress bar) — good for scripts
curl -s https://api.example.com/health

# Save to file
curl -o response.json https://api.example.com/data

# Save with remote filename
curl -O https://example.com/files/report.pdf

# Pretty-print JSON response
curl -s https://api.example.com/data | python3 -m json.tool
curl -s https://api.example.com/data | jq .

# Show only HTTP status code
curl -so /dev/null -w "%{http_code}" https://api.example.com/health

# Write-out multiple values
curl -so /dev/null -w "status=%{http_code} total=%{time_total}s\n" https://example.com

# Fail on HTTP errors (4xx/5xx) — useful in CI
curl -f https://api.example.com/health || echo "Health check failed"
```

---

## 10. SRE Patterns

### Health check script
```bash
#!/usr/bin/env bash
URL="${1:-http://localhost:8080/health}"
STATUS=$(curl -so /dev/null --connect-timeout 3 --max-time 5 \
  -w "%{http_code}" "$URL")

if [[ "$STATUS" == "200" ]]; then
  echo "OK ($STATUS)"
else
  echo "FAIL ($STATUS)" >&2
  exit 1
fi
```

### Latency baseline (10 requests)
```bash
for i in $(seq 1 10); do
  curl -so /dev/null -w "%{time_total}\n" https://api.example.com/health
done | awk '{sum+=$1; n++} END {printf "avg=%.3fs n=%d\n", sum/n, n}'
```

### Check if service is up before proceeding (k8s init containers / scripts)
```bash
until curl -sf http://postgres:5432 > /dev/null 2>&1; do
  echo "Waiting for postgres..."
  sleep 2
done
echo "postgres is up"
```

### Compare response times across environments
```bash
for env in dev staging prod; do
  printf "%-10s " "$env"
  curl -so /dev/null -w "status=%{http_code} ttfb=%{time_starttransfer}s total=%{time_total}s\n" \
    "https://$env.api.example.com/health"
done
```

### Test LB/ingress header injection
```bash
# Confirm X-Forwarded-For and X-Forwarded-Proto are being set
curl -s https://httpbin.org/get | python3 -m json.tool | grep -i forward
```

---

## 11. HTTP/2 Specific

```bash
# Force HTTP/2
curl --http2 https://example.com

# Force HTTP/1.1
curl --http1.1 https://example.com

# Check which version was used
curl -sv --http2 https://example.com 2>&1 | grep "Using HTTP"

# HTTP/2 without TLS (h2c — cleartext, rare)
curl --http2-prior-knowledge http://internal-service:8080
```

---

## 12. Proxy & Tunneling

```bash
# Route through HTTP proxy
curl -x http://proxy.internal:3128 https://example.com

# Route through SOCKS5 proxy
curl --socks5 127.0.0.1:1080 https://example.com

# Ignore proxy for specific host
curl --noproxy internal.example.com https://internal.example.com
```

---

## Quick Reference — Flags

| Flag | Meaning |
|---|---|
| `-v` | Verbose (show headers + TLS) |
| `-s` | Silent (no progress bar) |
| `-S` | Show errors even with `-s` |
| `-I` | HEAD request (headers only) |
| `-L` | Follow redirects |
| `-k` | Skip TLS cert verification |
| `-o FILE` | Write output to file |
| `-O` | Write output to remote filename |
| `-f` | Fail on HTTP errors (4xx/5xx) |
| `-X METHOD` | Set HTTP method |
| `-H "K: V"` | Add request header |
| `-d DATA` | Request body |
| `-u USER:PASS` | Basic auth |
| `-b COOKIE` | Send cookie |
| `-c FILE` | Save cookies to file |
| `-w FORMAT` | Write-out format string |
| `--retry N` | Retry N times on failure |
| `--connect-timeout N` | TCP connect timeout (seconds) |
| `--max-time N` | Total request timeout (seconds) |
| `--resolve H:P:IP` | Override DNS for host:port |
| `--http2` | Force HTTP/2 |
| `--http1.1` | Force HTTP/1.1 |
| `--tlsv1.3` | Force TLS 1.3 |
| `--cacert FILE` | Custom CA bundle |
| `--cert FILE` | Client certificate (mTLS) |

---

*Part of [layer4-networking-troubleshooting-runbooks](https://github.com/sharanch/layer4-networking-troubleshooting-runbooks)*
