# Save as hammerclient.py
import socket
import time

count = 0
while count < 2000:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 9999))
        s.recv(1024)
        s.close()  # explicit close — triggers TIME_WAIT
        count += 1
    except Exception as e:
        print(f"Error: {e}")

print("Done")
