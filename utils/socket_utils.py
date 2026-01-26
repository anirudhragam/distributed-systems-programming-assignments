import json
import struct
import socket

def send_message(socket: socket.socket, message: dict):
    """Function to length-prefix and send message"""
    payload = json.dumps(message).encode('utf-8')
    # Generating a header with the length of the payload in bytes
    header = struct.pack('!I', len(payload))
    # Send the header followed by the payload
    socket.sendall(header + payload)

def recv_n(socket: socket.socket, n: int):
    """Function to receive n bytes from the socket"""
    buf = b""
    while len(buf) < n:
        chunk = socket.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed")
        buf += chunk
    return buf

def recv_message(socket: socket.socket):
    """Function to receive length-prefixed message"""

    # Reading the 4-byte header to get the payload length
    header = recv_n(socket, 4)
    payload_length = struct.unpack('!I', header)[0]

    # Reading the actual payload based on the length
    payload = recv_n(socket, payload_length)
    return json.loads(payload.decode('utf-8'))