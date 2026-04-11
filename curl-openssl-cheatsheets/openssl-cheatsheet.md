# openssl Cheatsheet — SRE/DevOps Reference

> End-to-end: generating keys, creating certs, inspecting TLS, debugging PKI

---

## 1. The Mental Model

```
Private Key  →  CSR (Certificate Signing Request)  →  Certificate
    |                        |                              |
 stays on               sent to CA                   installed on
  server                for signing                    server
```

```
Root CA (self-signed)
  └── Intermediate CA (signed by Root)
        └── Server Certificate (signed by Intermediate)
              └── Presented to clients during TLS handshake
```

---

## 2. Generate Private Keys

```bash
# RSA 2048-bit (widely compatible)
openssl genrsa -out server.key 2048

# RSA 4096-bit (higher security, slower)
openssl genrsa -out server.key 4096

# RSA with passphrase protection
openssl genrsa -aes256 -out server.key 2048

# EC key (P-256) — preferred for TLS 1.3, smaller + faster than RSA
openssl ecparam -name prime256v1 -genkey -noout -out server.key

# EC key (P-384) — higher security
openssl ecparam -name secp384r1 -genkey -noout -out server.key

# View key details
openssl rsa -in server.key -text -noout
openssl ec -in server.key -text -noout

# Extract public key from private key
openssl rsa -in server.key -pubout -out server.pub
```

---

## 3. Certificate Signing Requests (CSR)

```bash
# Generate CSR from existing key
openssl req -new -key server.key -out server.csr

# Generate key + CSR in one command
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr

# Non-interactive CSR (supply subject on CLI)
openssl req -new -key server.key -out server.csr \
  -subj "/C=IN/ST=Telangana/L=Hyderabad/O=Example Corp/CN=api.example.com"

# CSR with Subject Alternative Names (SANs) — required for modern certs
openssl req -new -key server.key -out server.csr \
  -subj "/CN=api.example.com" \
  -addext "subjectAltName=DNS:api.example.com,DNS:www.example.com,IP:10.0.0.1"

# View CSR contents
openssl req -in server.csr -text -noout

# Verify CSR signature
openssl req -in server.csr -verify
```

---

## 4. Self-Signed Certificates

```bash
# Self-signed cert (dev/internal use)
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout server.key \
  -out server.crt \
  -days 365 \
  -subj "/CN=localhost"

# Self-signed with SANs (required by modern browsers)
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout server.key \
  -out server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:*.local,IP:127.0.0.1"

# Self-signed EC cert
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes \
  -keyout server.key \
  -out server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost"

# Sign CSR with your own key (create cert from existing CSR)
openssl x509 -req -in server.csr -signkey server.key -out server.crt -days 365
```

---

## 5. Build Your Own CA (Internal PKI)

### Step 1 — Create Root CA

```bash
# Root CA private key
openssl genrsa -aes256 -out ca.key 4096

# Root CA self-signed certificate (long validity — 10 years)
openssl req -x509 -new -nodes -key ca.key \
  -sha256 -days 3650 \
  -out ca.crt \
  -subj "/C=IN/O=Internal CA/CN=My Root CA"
```

### Step 2 — Issue Server Certificate from Root CA

```bash
# Server key + CSR
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=api.internal.example.com"

# Sign with Root CA (include SANs via ext file)
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=digitalSignature, keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:api.internal.example.com,DNS:*.internal.example.com
EOF

openssl x509 -req -in server.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt \
  -days 365 \
  -sha256 \
  -extfile server.ext
```

### Step 3 — Verify the chain

```bash
openssl verify -CAfile ca.crt server.crt
# should print: server.crt: OK
```

### Step 4 — Trust the Root CA on ubuntu-doge

```bash
sudo cp ca.crt /usr/local/share/ca-certificates/my-internal-ca.crt
sudo update-ca-certificates
```

---

## 6. Inspect Certificates

```bash
# View full cert details
openssl x509 -in server.crt -text -noout

# View specific fields
openssl x509 -in server.crt -noout -subject
openssl x509 -in server.crt -noout -issuer
openssl x509 -in server.crt -noout -dates        # validity window
openssl x509 -in server.crt -noout -fingerprint  # SHA1 fingerprint
openssl x509 -in server.crt -noout -serial
openssl x509 -in server.crt -noout -ext subjectAltName  # SANs

# SHA256 fingerprint
openssl x509 -in server.crt -noout -fingerprint -sha256

# View cert in PEM format
openssl x509 -in server.crt -text

# View DER format cert (binary)
openssl x509 -in server.der -inform DER -text -noout
```

---

## 7. Inspect Live TLS Connections

```bash
# Connect and show full TLS handshake + cert
openssl s_client -connect example.com:443

# Show full cert chain
openssl s_client -connect example.com:443 -showcerts

# Force TLS version
openssl s_client -connect example.com:443 -tls1_2
openssl s_client -connect example.com:443 -tls1_3

# SNI — required for virtual hosting (always use this)
openssl s_client -connect example.com:443 -servername example.com

# Check cert expiry dates
echo | openssl s_client -connect example.com:443 2>/dev/null \
  | openssl x509 -noout -dates

# Check subject + SANs of live cert
echo | openssl s_client -connect example.com:443 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName

# Check what cipher suite was negotiated
openssl s_client -connect example.com:443 2>/dev/null | grep "Cipher is"

# Test STARTTLS (email servers)
openssl s_client -connect smtp.gmail.com:587 -starttls smtp
openssl s_client -connect imap.gmail.com:993

# Test with client certificate (mTLS)
openssl s_client -connect api.example.com:443 \
  -cert client.crt -key client.key \
  -CAfile ca.crt

# Connect to internal service with custom CA
openssl s_client -connect internal.example.com:443 \
  -CAfile /path/to/internal-ca.crt \
  -servername internal.example.com
```

---

## 8. Certificate Expiry Monitoring

```bash
# Check expiry of a local cert file
openssl x509 -in server.crt -noout -enddate

# Days until expiry (script-friendly)
openssl x509 -in server.crt -noout -checkend $((30 * 86400)) \
  && echo "Valid for 30+ days" \
  || echo "EXPIRING within 30 days"

# Check expiry of live remote cert
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
  | openssl x509 -noout -dates

# Script: check multiple domains
for domain in example.com api.example.com cdn.example.com; do
  expiry=$(echo | openssl s_client -connect "$domain:443" \
    -servername "$domain" 2>/dev/null \
    | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  echo "$domain → $expiry"
done
```

---

## 9. Format Conversions

```bash
# PEM → DER (binary)
openssl x509 -in server.crt -outform DER -out server.der

# DER → PEM
openssl x509 -in server.der -inform DER -outform PEM -out server.crt

# PEM → PKCS#12 (bundles cert + key + chain — used by Java, Windows)
openssl pkcs12 -export \
  -in server.crt \
  -inkey server.key \
  -certfile ca.crt \
  -out server.p12 \
  -name "server cert"

# PKCS#12 → PEM
openssl pkcs12 -in server.p12 -out server.pem -nodes

# Extract cert only from PKCS#12
openssl pkcs12 -in server.p12 -nokeys -out server.crt

# Extract key only from PKCS#12
openssl pkcs12 -in server.p12 -nocerts -nodes -out server.key

# Combine cert + chain into one PEM bundle (order: server cert first)
cat server.crt intermediate.crt root.crt > bundle.crt

# Strip passphrase from private key
openssl rsa -in server-encrypted.key -out server.key
```

---

## 10. Verify Key-Cert-CSR Match

A cert and key that don't match will break TLS. Always verify:

```bash
# The modulus (or public key) must match across all three
openssl x509 -in server.crt -noout -modulus | md5sum
openssl rsa  -in server.key -noout -modulus | md5sum
openssl req  -in server.csr -noout -modulus | md5sum

# All three hashes must be identical
# If any differ → wrong key/cert combination
```

---

## 11. Symmetric Encryption (Files)

```bash
# Encrypt a file
openssl enc -aes-256-cbc -salt -pbkdf2 -in secret.txt -out secret.enc

# Decrypt
openssl enc -d -aes-256-cbc -pbkdf2 -in secret.enc -out secret.txt

# Encrypt with explicit key + IV (for scripting)
openssl enc -aes-256-cbc -K $KEY_HEX -iv $IV_HEX -in plain.txt -out cipher.bin
```

---

## 12. Hashing & Digests

```bash
# Hash a file
openssl dgst -sha256 file.tar.gz
openssl dgst -sha512 file.tar.gz
openssl dgst -md5 file.tar.gz        # avoid for security — use for checksums only

# HMAC
openssl dgst -sha256 -hmac "secret-key" file.txt

# Hash a string
echo -n "hello world" | openssl dgst -sha256

# Base64 encode/decode
echo "hello world" | openssl base64
echo "aGVsbG8gd29ybGQ=" | openssl base64 -d
```

---

## 13. Asymmetric Encryption & Signing

```bash
# Sign a file with private key
openssl dgst -sha256 -sign server.key -out file.sig file.txt

# Verify signature with public key
openssl dgst -sha256 -verify server.pub -signature file.sig file.txt

# Encrypt with public key (small payloads only)
openssl rsautl -encrypt -inkey server.pub -pubin -in secret.txt -out secret.enc

# Decrypt with private key
openssl rsautl -decrypt -inkey server.key -in secret.enc -out secret.txt
```

---

## 14. Test a Local TLS Server

```bash
# Spin up a quick TLS server on port 4433
openssl s_server -accept 4433 -cert server.crt -key server.key -www

# Connect to it from another terminal
openssl s_client -connect localhost:4433

# Serve a specific file
openssl s_server -accept 4433 -cert server.crt -key server.key < response.html
```

---

## 15. OCSP — Check Certificate Revocation

```bash
# Get OCSP URI from cert
openssl x509 -in server.crt -noout -ocsp_uri

# Check revocation status
openssl ocsp \
  -issuer intermediate.crt \
  -cert server.crt \
  -url http://ocsp.example.com \
  -resp_text
```

---

## 16. Common SRE Workflows

### Debug a broken TLS handshake
```bash
# Step 1 — can we connect at all?
openssl s_client -connect api.example.com:443 -servername api.example.com

# Step 2 — is the cert chain complete?
openssl s_client -connect api.example.com:443 -showcerts 2>/dev/null \
  | grep -E "subject|issuer"

# Step 3 — verify chain against known CA
openssl verify -CAfile ca-bundle.crt server.crt

# Step 4 — check cert expiry
echo | openssl s_client -connect api.example.com:443 2>/dev/null \
  | openssl x509 -noout -dates

# Step 5 — key/cert mismatch?
openssl x509 -in server.crt -noout -modulus | md5sum
openssl rsa  -in server.key -noout -modulus | md5sum
```

### Rotate a certificate
```bash
# 1. Generate new key
openssl genrsa -out server-new.key 2048

# 2. Generate CSR
openssl req -new -key server-new.key -out server-new.csr \
  -subj "/CN=api.example.com" \
  -addext "subjectAltName=DNS:api.example.com"

# 3. Submit CSR to CA → get server-new.crt

# 4. Verify new cert matches new key
openssl x509 -in server-new.crt -noout -modulus | md5sum
openssl rsa  -in server-new.key -noout -modulus | md5sum

# 5. Verify chain
openssl verify -CAfile ca-bundle.crt server-new.crt

# 6. Deploy and reload (nginx example)
sudo cp server-new.crt /etc/nginx/ssl/server.crt
sudo cp server-new.key /etc/nginx/ssl/server.key
sudo nginx -t && sudo systemctl reload nginx
```

### Check what ciphers a server supports
```bash
# Quick cipher scan (bash loop)
for cipher in $(openssl ciphers 'ALL:eNULL' | tr ':' ' '); do
  result=$(echo -n | openssl s_client -cipher "$cipher" \
    -connect example.com:443 2>/dev/null | grep "Cipher is")
  [ -n "$result" ] && echo "$cipher: $result"
done
```

---

## Quick Reference — Key Flags

| Flag | Meaning |
|---|---|
| `-text` | Human-readable output |
| `-noout` | Don't print the encoded object |
| `-nodes` | No DES encryption on private key |
| `-new` | Generate new CSR or key |
| `-x509` | Output self-signed cert instead of CSR |
| `-days N` | Validity period |
| `-CAfile` | Trusted CA bundle for verification |
| `-showcerts` | Show full cert chain |
| `-servername` | SNI hostname for s_client |
| `-connect HOST:PORT` | Target for s_client |
| `-inform DER/PEM` | Input format |
| `-outform DER/PEM` | Output format |
| `-subj` | Certificate subject (DN) |
| `-addext` | Add extension (SANs, etc.) |
| `-sha256` | Use SHA-256 digest |
| `-modulus` | Print RSA modulus (for matching) |

---

## Common File Extensions

| Extension | Contents |
|---|---|
| `.key` | Private key (PEM) |
| `.crt` / `.cer` | Certificate (PEM or DER) |
| `.csr` | Certificate Signing Request |
| `.pem` | Generic PEM container (can hold anything) |
| `.der` | Binary DER encoded cert or key |
| `.p12` / `.pfx` | PKCS#12 bundle (cert + key + chain) |
| `.p7b` | PKCS#7 cert chain (no private key) |
| `ca-bundle.crt` | Concatenated CA chain |

---

*Part of [layer4-networking-troubleshooting-runbooks](https://github.com/sharanch/layer4-networking-troubleshooting-runbooks)*
