import socket

HEADER = 64
SERVER, PORT = socket.gethostbyname(socket.gethostname()), 5500
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MSG = "!DISCONNECTED"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(ADDR)

def send(msg):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    client.send(send_length)
    client.send(message)
    print(client.recv(2048).decode(FORMAT))
    print()

send('Hello World!')
input()
send('Hello Everyone!')
input()
send('Hello Hanz!')

send(DISCONNECT_MSG)