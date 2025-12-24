import socket

class TitanClient:
    def __init__(self, host='localhost', port=6379):
        self.host = host
        self.port = port
        self.sock = None

    def __enter__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.sock:
            self.sock.close()

    def set(self, key: str, value: str):
        self.sock.sendall(f"SET {key} {value}\n".encode())
        return self.sock.recv(1024).decode().strip()

    def get(self, key: str):
        self.sock.sendall(f"GET {key}\n".encode())
        return self.sock.recv(4096).decode().strip()