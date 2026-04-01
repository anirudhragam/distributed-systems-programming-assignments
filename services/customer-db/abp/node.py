import logging
import threading
import time
from abp.messages import (build_request, build_sequence, build_status, build_retransmit_request, 
                          build_retransmit_sequence, request_id_from_msg)
from abp.transport import UDPTransport
from abp.executor import SQLExecutor

logger = logging.getLogger(__name__)

class ABPNode:

    def __init__(self, node_id: int, peers: list, db_pool, udp_port: int):

        # node_id  : node index starting from 0
        # peers    : list of (host, udp_port) of all replicas
        # db_pool  : psycopg2 DB connection pool;
        # udp_port : UDP port this node binds to

        self.node_id = node_id
        self.n = len(peers)
        self.peers = peers

        host = peers[node_id][0]
        self.transport = UDPTransport(host, udp_port)
        self.executor = SQLExecutor(db_pool)

        self.lock = threading.Lock()

        self.local_seq = 0

        self.all_requests: dict = {}
       
        # Subset of all_requests that have not been asssigned a global sequence number
        self.pending_requests: dict = {}
        
        # Contains mappings from global_seq -> SEQUENCE msg
        self.sequences: dict = {}
        
        # next global seq the sequencer thread should try to assign
        self.next_seq_to_assign = 0

        self.next_to_deliver = 0
        self.delivered: set = set()

        # Set of rids (sender_id, local_seq) that have been assigned a global_seq.
        # Used to prevent adding already-sequenced requests back into pending_requests.
        self.sequenced_rids: set = set()

        # Contains mappings from node_id -> highest global_seq that node has fully received (REQUEST + SEQUENCE)
        # Initially -1 implying no messages received from that node yet
        self.peer_received_up_to: dict = {i: -1 for i in range(self.n)}

        # Contains mappings from (sender_id, local_seq) -> threading.Event (set by delivery_thread)
        self.pending_events: dict = {}
        # Contains mappings from (sender_id, local_seq) → SQL result dict
        self.delivery_results: dict = {}

    def start(self):
        threads = [
            threading.Thread(target=self.recv_thread,       daemon=True, name="abp-recv"),
            threading.Thread(target=self.sequencer_thread,  daemon=True, name="abp-sequencer"),
            threading.Thread(target=self.delivery_thread,   daemon=True, name="abp-delivery"),
            threading.Thread(target=self.status_thread,     daemon=True, name="abp-status"),
            threading.Thread(target=self.retransmit_thread, daemon=True, name="abp-retransmit"),
        ]
        for t in threads:
            t.start()
        logger.info("ABPNode %d started (%d peers)", self.node_id, self.n)

    def recv_thread(self):
        """Blocking loop that calls transport.recv() and dispatches based on msg["type"]"""

        while True:
            msg, addr = self.transport.recv()
            t = msg.get("type")
            if   t == "REQUEST":    self.handle_request(msg)
            elif t == "SEQUENCE":   self.handle_sequence(msg)
            elif t == "STATUS":     self.handle_status(msg)
            elif t == "RETRANSMIT": self.handle_retransmit(msg, addr)
            else:
                logger.warning("Unknown message type: %s", t)

    def handle_request(self, msg):
        with self.lock:
            self.update_peer_progress(msg["sender_id"], msg["received_up_to"])
            rid = request_id_from_msg(msg)
            if rid not in self.all_requests:
                self.all_requests[rid] = msg
                if rid not in self.sequenced_rids:
                    self.pending_requests[rid] = msg

    def update_peer_progress(self, node_id: int, received_up_to: int):
        """ Function that updates a peer's progress (highest global_seq it has received up to)"""
        if received_up_to > self.peer_received_up_to.get(node_id, -1):
            self.peer_received_up_to[node_id] = received_up_to

    def handle_sequence(self, msg):
        with self.lock:
            self.update_peer_progress(msg["sequencer_id"], msg["received_up_to"])
            g = msg["global_seq"]
            if g not in self.sequences:
                self.sequences[g] = msg
                rid = tuple(msg["request_id"])
                self.sequenced_rids.add(rid)
                self.pending_requests.pop(rid, None)
            # Advance next_seq_to_assign past this sequence so the sequencer
            # thread can reach its own turn (k where k % n == node_id).
            if g + 1 > self.next_seq_to_assign:
                self.next_seq_to_assign = g + 1

    def handle_status(self, msg):
        with self.lock:
            self.update_peer_progress(msg["sender_id"], msg["received_up_to"])

    def handle_retransmit(self, msg, addr):
        with self.lock:
            if msg["retransmit_type"] == "REQUEST":
                rid = tuple(msg["request_id"])
                cached = self.all_requests.get(rid)
            else:
                cached = self.sequences.get(msg["global_seq"])
        if cached:
            self.transport.broadcast(cached, self.peers)
    def sequencer_thread(self):
        while True:
            with self.lock:
                k = self.next_seq_to_assign

                # Only act when it's our turn
                if k % self.n != self.node_id:
                    pass  

                # Precondition 1: all prior SEQUENCE messages exist
                elif not all(g in self.sequences for g in range(k)):
                    pass  # waiting for earlier sequences

                # Precondition 2: all prior requests referenced by sequences are in all_requests
                elif any(tuple(self.sequences[g]["request_id"]) not in self.all_requests
                        for g in range(k)):
                    pass  # waiting for earlier requests

                else:
                    # Pick a candidate from pending_requests:
                    # must not have any earlier unsequenced request from the same sender
                    candidate = None
                    for (sid, lseq), req in sorted(self.pending_requests.items()):
                        has_earlier = any(
                            lseq2 < lseq and (sid, lseq2) in self.pending_requests
                            for (sid2, lseq2) in self.pending_requests
                            if sid2 == sid
                        )
                        if not has_earlier:
                            candidate = ((sid, lseq), req)
                            break

                    if candidate:
                        rid, req = candidate
                        seq_msg = build_sequence(k, rid, self.node_id,
                                                self.my_received_up_to())
                        self.sequences[k] = seq_msg
                        self.sequenced_rids.add(rid)
                        del self.pending_requests[rid]
                        self.next_seq_to_assign = k + 1

                        # broadcast outside lock — release first
                        self.lock.release()
                        try:
                            self.transport.broadcast(seq_msg, self.peers)
                        finally:
                            self.lock.acquire()

            time.sleep(0.001)

    def delivery_thread(self):
        while True:
            req_msg = None
            rid = None

            with self.lock:
                s = self.next_to_deliver

                if s in self.sequences:
                    rid = tuple(self.sequences[s]["request_id"])

                    if rid in self.all_requests:
                        # Majority condition: ≥ ⌊n/2⌋+1 nodes have received_up_to ≥ s
                        acks = sum(1 for v in self.peer_received_up_to.values() if v >= s)
                        if acks >= (self.n // 2 + 1):
                            req_msg = self.all_requests[rid]
                            self.next_to_deliver += 1

            if req_msg:
                # Execute SQL outside lock — can block on DB I/O
                result = self.executor.execute(
                    req_msg["payload"]["method"],
                    req_msg["payload"]["args"]
                )

                with self.lock:
                    self.delivered.add(rid)
                    # Update our own progress AFTER delivery
                    self.peer_received_up_to[self.node_id] = self.next_to_deliver - 1

                    if rid in self.pending_events:
                        self.delivery_results[rid] = result
                        self.pending_events[rid].set()
            else:
                time.sleep(0.001)

    def status_thread(self):
        while True:
            time.sleep(0.02)
            with self.lock:
                rut = self.my_received_up_to()
            status_msg = build_status(self.node_id, rut)
            self.transport.broadcast(status_msg, self.peers)

    def retransmit_thread(self):
        while True:
            time.sleep(0.5)
            to_send = []

            with self.lock:
                # Gap type 1: SEQUENCE exists but its REQUEST hasn't arrived
                for g, seq_msg in self.sequences.items():
                    rid = tuple(seq_msg["request_id"])
                    if rid not in self.all_requests:
                        original_sender = rid[0]
                        to_send.append(
                            build_retransmit_request(self.node_id, original_sender, rid)
                        )

                # Gap type 2: missing SEQUENCE — have seq s+1 but not s
                known_seqs = set(self.sequences.keys())
                for g in known_seqs:
                    if g > 0 and (g - 1) not in known_seqs:
                        expected_sequencer = (g - 1) % self.n
                        to_send.append(
                            build_retransmit_sequence(self.node_id, expected_sequencer, g - 1)
                        )

            for msg in to_send:
                target_id = msg["target_id"]
                target_host, target_port = self.peers[target_id]
                self.transport.send(msg, target_host, target_port)

    def my_received_up_to(self) -> int:
        """
        Returns the highest contiguous global_seq s such that
        sequences and their referenced requests all exist.
        -1 if nothing received yet.
        Called inside the lock.
        """
        s = -1
        while True:
            candidate = s + 1
            if candidate not in self.sequences:
                break
            rid = tuple(self.sequences[candidate]["request_id"])
            if rid not in self.all_requests:
                break
            s = candidate
        return s
    
    def submit_write(self, method: str, args: dict) -> dict:
        """
        Called by gRPC handler. Blocks until the write is delivered by
        delivery_thread (or times out after 30s).
        Returns the SQL result dict.
        """
        with self.lock:
            lseq = self.local_seq
            self.local_seq += 1
            rid = (self.node_id, lseq)
            event = threading.Event()
            self.pending_events[rid] = event
            req_msg = build_request(
                self.node_id, lseq, method, args,
                self.my_received_up_to()
            )
            self.all_requests[rid] = req_msg
            self.pending_requests[rid] = req_msg

        self.transport.broadcast(req_msg, self.peers)
        delivered = event.wait(timeout=30.0)

        with self.lock:
            result = self.delivery_results.pop(rid, None)
            self.pending_events.pop(rid, None)
            if not delivered:
                self.pending_requests.pop(rid, None)
                self.all_requests.pop(rid, None)

        if not delivered or result is None:
            return {"success": False, "error_message": "ABP timeout — write not delivered"}
        return result
    

