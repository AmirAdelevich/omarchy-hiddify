"""Linux loopback connection ownership checks before sending HTTP credentials."""
import http.client
import pathlib
import socket


def socket_address(address):
    host, port = address
    if host != '127.0.0.1':
        raise OSError('Expected IPv4 loopback connection')
    return socket.inet_aton(host)[::-1].hex().upper() + f':{port:04X}'


def trusted_peer_in_table(table, local, remote, allowed_uids):
    for line in table.splitlines():
        columns = line.split()
        if len(columns) < 10 or columns[1:4] != [remote, local, '01']:
            continue
        try:
            return int(columns[7]) in allowed_uids
        except ValueError:
            return False
    return False


def verify_peer(connection, allowed_uids):
    local = socket_address(connection.getsockname())
    remote = socket_address(connection.getpeername())
    table = pathlib.Path('/proc/net/tcp').read_text()
    if not trusted_peer_in_table(table, local, remote, allowed_uids):
        raise OSError('Untrusted local API peer')


class AuthenticatedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, port, allowed_uids, timeout=1.5):
        super().__init__('127.0.0.1', port, timeout=timeout)
        self.allowed_uids = allowed_uids

    def connect(self):
        super().connect()
        try:
            verify_peer(self.sock, self.allowed_uids)
        except Exception:
            self.close()
            raise
