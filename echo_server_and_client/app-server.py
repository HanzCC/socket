import sys
import socket
import selectors
import traceback
import libserver


sel = selectors.DefaultSelector()

def accept_wrapper(sock):
    conn, addr = sock.accept()
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    message = libserver.Message(sel, conn, addr)
    # data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
    # events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, selectors.EVENT_READ, data=message)

# def service_connection(key, mask):
#     sock = key.fileobj
#     data = key.data
#     if mask & selectors.EVENT_READ:
#         recv_data = sock.recv(1024)
#         if recv_data:
#             data.outb += recv_data
#         else:
#             print(f"Closing connection to {data.addr}")
#             sel.unregister(sock)
#             sock.close()
#     if mask & selectors.EVENT_WRITE:
#         if data.outb:
#             print(f"Echoing {data.outb!r} to {data.addr}")
#             sent = sock.send(data.outb)
#             data.outb = data.outb[sent:]

# print(sys.argv)
# sys_argv = sys.argv[1:]
if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <host> <port>")
    sys.exit(1)
    
host, port =  sys.argv[1], int(sys.argv[2])

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
lsock.bind((host, port))
lsock.listen()
print(f"Listening on {(host, port)}")
lsock.setblocking(False)
# sel.register() - register the socket to be monitored with sel.select() for the events that you're interested in,
#                  In this case, the read event - selectors.EVENT_READ
sel.register(lsock, selectors.EVENT_READ, data=None)

# Event loop
try:
    while True:
        # blocks until there are sockets ready for I/O.
        # Return a list of tuples, one tuples for each socket.
        # Each tuple contains a key, and mask object. 
        events = sel.select(timeout=None)
        # key - Selectorkey namedtuple that contains a the socket obj(fileobj) and data object. 
        # mask - "Event Mask" of the operations/events that are ready.
        # "Event mask" == To avoid flooding the clients with events in which they have no interest, they must explicitly
        #               tell the server which events they are interested in. This is done 
        #               by providing the event_mask attribute.
        for key, mask in events:
            # decide the action taken based on the type of socket (listening | client)
            if key.data is None:   # listening socket
                accept_wrapper(key.fileobj)   # use this func to accept a new socket and register it with the selectors 
            else:   # key.data is not none - client socket thats already accepted, need to services it
                message = key.data   # use this func with key, mask to operate on the socket.
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.addr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()