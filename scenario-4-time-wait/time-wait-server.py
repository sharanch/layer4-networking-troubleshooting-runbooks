# Save as time_wait_server.py
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(100)
print("Listening on port 9999...")

while True:
    conn, addr = server.accept()
    conn.send(b"hello\n")
    conn.close()  # server closes immediately — intentionally short lived
