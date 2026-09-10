"""PC-side asynchronous client for the M7 controller TCP protocol.

Keep the client import lazy: the i.MX6ULL server imports only ``protocol`` and
does not need to transfer the PC reconnect client to the constrained target.
"""

__all__ = ["ControllerClient", "ControllerClientError", "ControllerTimeout"]


def __getattr__(name):
    """Preserve the package-level client API without importing it for protocol-only users."""

    if name in __all__:
        from .controller_client import ControllerClient, ControllerClientError, ControllerTimeout

        return {
            "ControllerClient": ControllerClient,
            "ControllerClientError": ControllerClientError,
            "ControllerTimeout": ControllerTimeout,
        }[name]
    raise AttributeError("module {0!r} has no attribute {1!r}".format(__name__, name))
