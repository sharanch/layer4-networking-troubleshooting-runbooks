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
