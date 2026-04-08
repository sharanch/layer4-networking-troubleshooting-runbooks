# This starts a simple HTTP server on port 9999
terminal 1
dd if=/dev/zero of=largefile.bin bs=1M count=100
python3 -m http.server 9999
# Client Side - terminal 2
curl http://localhost:9999/largefile.bin --limit-rate 10k -o /dev/null
