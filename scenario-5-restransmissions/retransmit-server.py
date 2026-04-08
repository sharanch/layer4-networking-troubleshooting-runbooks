# Save as retransmit-server.py
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('0.0.0.0', 9999))
server.listen(5)
print("Listening...")

while True:
    conn, addr = server.accept()
    # Send a chunk of data
    conn.send(b"X" * 100000)
    conn.close()
