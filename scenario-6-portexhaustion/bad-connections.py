# bad_client.py
import socket, time

COUNT = 0
while True:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 9999))
        s.sendall(b'hello')
        s.recv(1024)
        s.close()          # closes, but port enters TIME_WAIT
        COUNT += 1
        if COUNT % 500 == 0:
            print(f"{COUNT} connections made")
    except Exception as e:
        print(f"FAILED at {COUNT}: {e}")
        break
