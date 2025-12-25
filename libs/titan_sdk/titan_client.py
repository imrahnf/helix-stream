import socket
import struct

class TitanClient:
    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port
        self.sock = None

    def __enter__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._send_receive("VERSION:1.0") 
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sock:
            self.sock.close()

    def _send_receive(self, cmd_str: str):
        # Length prefixe
        msg_bytes = cmd_str.encode('utf-8')
        
        # Pack length as 4-byte Big-Endian Int
        header = struct.pack('>I', len(msg_bytes))
        self.sock.sendall(header + msg_bytes)

        # Read 4-byte response header
        resp_header = self._recv_all(4)
        if not resp_header: 
            return None
        
        resp_len = struct.unpack('>I', resp_header)[0]
        
        # Read the actual response payload
        data = self._recv_all(resp_len)
        return data.decode('utf-8')

    def _recv_all(self, n):
        # Helper to handle TCP stream fragmentation
        data = bytearray()
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data

    def check(self, key: str):
        # Synchronous L1 cache lookup
        return self._send_receive(f"CHECK:{key}")

    def enqueue(self, key: str, sequence: str):
        # Registers a new task for the Data Plane
        return self._send_receive(f"ENQUEUE:{key}:{sequence}")

    def status(self, key: str):
        # Returns current state (QUEUED | DONE)"
        return self._send_receive(f"STATUS:{key}")