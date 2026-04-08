# Save as buggy_server.py
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(5)
print("Listening on port 9999...")

while True:
    conn, addr = server.accept()
    print(f"Connection from {addr}")
    # Intentional bug — we never call conn.close()
    # Remote can close their side, we never close ours
