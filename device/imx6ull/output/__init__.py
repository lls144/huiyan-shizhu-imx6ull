"""Asynchronous, least-privilege branch-output adapters."""

from .branch_output import BranchOutputDispatcher, NullBranchOutputBackend, UnixSocketBranchOutputBackend
from .protocol import OUTPUT_PROTOCOL_VERSION, OutputProtocolError, decode_output_event, encode_output_event

__all__ = [
    "BranchOutputDispatcher",
    "NullBranchOutputBackend",
    "OUTPUT_PROTOCOL_VERSION",
    "OutputProtocolError",
    "UnixSocketBranchOutputBackend",
    "decode_output_event",
    "encode_output_event",
]
