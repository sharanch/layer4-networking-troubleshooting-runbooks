# server.py
import socket, threading, time

def handle(conn):
    conn.recv(1024)
    conn.sendall(b'ok')
    time.sleep(0.1)        # <-- hold connection open briefly
    conn.close()

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', 9999))
s.listen(500)
print('Listening on 9999...')
while True:
    conn, _ = s.accept()
    threading.Thread(target=handle, args=(conn,)).start()
