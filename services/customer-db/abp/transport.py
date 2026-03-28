"""
UDP transport layer for the ABP protocol.
"""

import socket
import logging
from abp.messages import encode, decode

logger = logging.getLogger(__name__)


RECV_BUFSIZE = 65_507


class UDPTransport:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        logger.info("UDPTransport bound to %s:%d", host, port)


    def send(self, msg: dict, host: str, port: int) -> None:
        """Serialise msg and send it to (host, port)"""
        try:
            data = encode(msg)
            self.sock.sendto(data, (host, port))
        except Exception as exc:
            logger.warning("send to %s:%d failed: %s", host, port, exc)

    def broadcast(self, msg: dict, peers: list) -> None:
        """Method to broadcast msg to every (host, port) pair in peers"""

        for host, port in peers:
            self.send(msg, host, port)

    def recv(self) -> tuple:
        """
        Block until a UDP datagram arrives, then return (msg_dict, (host, port)).
        """
        while True:
            try:
                data, addr = self.sock.recvfrom(RECV_BUFSIZE)
                msg = decode(data)
                return msg, addr
            except (ValueError, KeyError) as exc:
                logger.warning("Malformed datagram from %s: %s", addr, exc)
                # skip and wait for the next datagram
            except Exception as exc:
                logger.error("recv error: %s", exc)
                raise


    def close(self) -> None:
        """Close the underlying socket. Called on node shutdown."""
        try:
            self.sock.close()
        except Exception:
            pass
