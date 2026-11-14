import socket
import threading
import unittest

from local_peer import AuthenticatedHTTPConnection, socket_address, trusted_peer_in_table


class LocalPeerTests(unittest.TestCase):
    def test_trusted_uid_must_own_the_exact_established_peer(self):
        local = '0100007F:CAFE'
        remote = '0100007F:4664'
        row = f'0: {remote} {local} 01 0 0 0 1000 0 12345'
        self.assertTrue(trusted_peer_in_table(row, local, remote, {0, 1000}))
        for table in (row.replace('1000', '1001'), row.replace(' 01 ', ' 0A '),
                      row.replace(local, '0100007F:BEEF'), row.replace('1000', 'invalid'), ''):
            self.assertFalse(trusted_peer_in_table(table, local, remote, {0, 1000}))

    def test_impostor_http_server_does_not_receive_authorization(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            received = []

            def capture():
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    received.append(connection.recv(4096))

            thread = threading.Thread(target=capture)
            thread.start()
            connection = AuthenticatedHTTPConnection(listener.getsockname()[1], {999999})
            with self.assertRaises(OSError):
                connection.request('GET', '/proxies', headers={'Authorization': 'Bearer fixture-secret'})
            connection.close()
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(received, [b''])

    def test_current_user_http_server_remains_usable(self):
        import os
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            received = []

            def reply():
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    received.append(connection.recv(4096))
                    connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')

            thread = threading.Thread(target=reply)
            thread.start()
            connection = AuthenticatedHTTPConnection(listener.getsockname()[1], {os.getuid()})
            try:
                connection.request('GET', '/proxies', headers={'Authorization': 'Bearer fixture-secret'})
                self.assertEqual(connection.getresponse().read(), b'{}')
            finally:
                connection.close()
                thread.join(timeout=3)
            self.assertIn(b'Bearer fixture-secret', received[0])

    def test_non_loopback_rejected(self):
        with self.assertRaises(OSError):
            socket_address(('192.0.2.1', 1234))
