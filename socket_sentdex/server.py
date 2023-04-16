import socket

HEADERSIZE = 10
HOST = socket.gethostbyname(socket.gethostname())
PORT = 5050
ADDR = (HOST, PORT)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(ADDR)
s.listen(5)

while True:
    clientsocket, address = s.accept()
    print(f"Connection from {address} has been established")

    msg = "Welcome to the server!"
    msg = f"{len(msg) :<{HEADERSIZE}}" + msg

    clientsocket.send(bytes(msg, "utf-8"))