import sys
import selectors 
import json
import io
# This module converts between Python values and C structs represented as Python bytes objects.
import struct


request_search = {}

class Message:
    def __init__(self, selector, socket, address, request):
        self.selector = selector
        self.socket = socket
        self.address = address
        self.request = request 
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request_queued = False
        self._jsonheader_len = None
        self.jsonheader = None
        self.response = None

    def _set_selector_events_mask(self, mode):
        """Set selector to listen for events: mode is 'r','w', or 'rw'."""
        if mode == 'r':
            events = selectors.EVENT_READ
        elif mode == 'w':
            events = selectors.EVENT_WRITE
        elif mode == 'rw':
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}")
        self.selector.modify(self.sock, events, data=self)

    def _read(self):
        try:
            data = self.socket.recv(4096)
        except BlockingIOError:
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed")
            
    def _write(self):
        if self._send_buffer:
            print(f"Sending {self._send_buffer!r} to {self.address}")
            try:
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)
    
    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj
    
    def _create_message(
            self, *, content_bytes, content_type, content_encoding
    ):
        jsonheader = {
            'byteorder': sys.byteorder,
            'content-type': content_type,
            'content-encoding': content_encoding,
            'content-length': len(content_bytes)
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message
    
    def _create_respone_json_content(self):
        action = self.request.get('action')
        if action == 'search':
            query = self.request.get('value')
            answer = request_search.get(query) or f"No match for {query}."
            content = {"result": answer}
        else:
            content = {"result": f"Error: invalid action '{action}'."}
        content_encoding = 'utf-8'
        response = {
            "content_bytes": self._json_encode(content, content_encoding),
            "content_types": "text/json",
            "content_encoding": content_encoding,
        }
        return response
    
    def _process_response_json_content(self):
        content = self.response
        result = content.get("result")
        print(f"Got result: {result}")
    
    def _process_response_binary_content(self):
        content = self.response
        print(f"Got reponse: {content!r}")


    # self.process_events - will be called many times over the life of the connection.
    #    make sure any methods that should be called once are either checking a state variables themselves/
    #       the state variable set by the method is checked by the caller
    def process_events(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def read(self):
        self._read()

        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_response()

    # The client initiates a connection to the server and sends a request first,
    #    the state variable - self._request_queued - is checked.
    # If a request hasn't queued, it calls self.queue_request()
    def write(self):
        if not self._request_queued:
            self.queue_request()
        self.write()

        # if the request has been queued,
        #    and the send_buffer is empty,
        #      done writing, only interested in read events.
        if self._request_queued:
            if not self._send_buffer:
                self._set_selector_events_mask("r")

    def close(self):
        print(f"Closing connection to {self.address}")
        try:
            self.selector.unregister(self.socket)
        except Exception as e:
            print(f"Error: selector.unregister() exception for "
                  f"{self.address}: {e!r}")
        try:
            self.socket.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.address}: {e!r}")
        finally:
            self.sock = None

    # Creates the request and writes it to the send buffer.
    #    alse set the state variable self._request_queued so that it only called once.
    def queue_request(self):
        content = self.request["content"]
        content_type = self.request["type"]
        content_encoding = self.request["encoding"]
        if content_type == 'text/json':
            req = {
                "content_bytes": self._json_encode(content, content_encoding),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        else:
            req = {
                "content_bytes": content,
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        message = self._create_message(**req)
        self._send_buffer += message
        self._request_queued = True

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding"
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")
                
    def process_reponse(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            self.response = self._json_decode(data, encoding)
            print(f"Received response {self.response!r} from {self.address}")
            self._process_response_json_content()
        else:
            self.response = data
            print(f"Received {self.jsonheader['content-type']} "
                  f"response from {self.address}")
            self._process_response_binary_content()
        self.close()