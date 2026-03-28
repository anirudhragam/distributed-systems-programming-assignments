"""
Message types:
  REQUEST    — broadcast by whichever node receives a gRPC write
  SEQUENCE   — broadcast by the designated sequencer (global_seq k → node k mod n)
  STATUS     — periodic heartbeat so majority tracking advances even when quiet
  RETRANSMIT — NAK asking the original sender to re-send a missing message
"""

import json


def build_request(sender_id: int, local_seq: int, method: str, args: dict, received_up_to: int) -> dict:
    """Function to build a REQUEST message"""
   
    # sender_id : node ID of the replica that received the client gRPC call
    # local_seq : monotonically increasing counter on that sender
    # method : name of the write operation, e.g. "CreateSeller"
    # args : dict of arguments for the operation (must be JSON-serialisable)
    # received_up_to : highest global seq this node has fully received (request + seq msg)

    return {
        "type": "REQUEST",
        "sender_id": sender_id,
        "local_seq": local_seq,
        "payload": {"method": method, "args": args},
        "received_up_to": received_up_to,  
    }


def build_sequence(global_seq: int, request_id: tuple, sequencer_id: int, received_up_to: int) -> dict:
    """Function to build a SEQUENCE message"""

    # global_seq : the globally monotonic sequence number being assigned to the REQUEST with request_id
    # request_id : (sender_id, local_seq) of the REQUEST msg being sequenced
    # sequencer_id : node ID of the replica sending this (responsible for sequencing)
    # received_up_to : highest global seq this sequencer has fully received

    return {
        "type": "SEQUENCE",
        "global_seq": global_seq,
        "request_id": list(request_id), 
        "sequencer_id": sequencer_id,
        "received_up_to": received_up_to,
    }


def build_status(sender_id: int, received_up_to: int) -> dict:
    """ Fucntion to build a STATUS heartbeat message"""

    #Broadcast periodicall so that the majority conditioncan be checked even when no writes are currently happening.
    return {
        "type": "STATUS",
        "sender_id": sender_id,
        "received_up_to": received_up_to,
    }


def build_retransmit_request(requester_id: int, target_id: int, request_id: tuple) -> dict:
    """Function to build a RETRANSMIT message asking to re-send a REQUEST"""

    # requester_id : node that detected the gap
    # target_id : original sender of the REQUEST (request_id[0])
    # request_id : (sender_id, local_seq) of the missing REQUEST

    return {
        "type": "RETRANSMIT",
        "requester_id": requester_id,
        "target_id": target_id,
        "retransmit_type": "REQUEST",
        "request_id": list(request_id),
    }


def build_retransmit_sequence(requester_id: int, target_id: int, global_seq: int) -> dict:
    """ Function to build a RETRANSMIT message asking to re-send a SEQUENCE"""
    return {
        "type": "RETRANSMIT",
        "requester_id": requester_id,
        "target_id": target_id,
        "retransmit_type": "SEQUENCE",
        "global_seq": global_seq,
    }


def encode(msg: dict) -> bytes:
    """Function to serialise a message dict to JSON for UDP transmission"""
    return json.dumps(msg, separators=(",", ":")).encode("utf-8")


def decode(data: bytes) -> dict:
    """Function to deserialise raw UDP bytes back to a message dict"""
    return json.loads(data.decode("utf-8"))


def request_id_from_msg(msg: dict) -> tuple:
    if msg["type"] == "REQUEST":
        return (msg["sender_id"], msg["local_seq"])
    
    return tuple(msg["request_id"])
