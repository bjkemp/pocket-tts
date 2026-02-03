"""
Temporary patch to disable SSL verification for HuggingFace downloads.
This is necessary in corporate environments with SSL-intercepting firewalls.
"""
import ssl
import httpx


def disable_ssl_verification():
    """Monkey-patch httpx to disable SSL verification."""
    # Store original Client class
    original_client_init = httpx.Client.__init__

    def patched_init(self, *args, **kwargs):
        # Force verify=False for all httpx clients
        kwargs['verify'] = False
        return original_client_init(self, *args, **kwargs)

    # Apply the patch
    httpx.Client.__init__ = patched_init
    print("⚠️  SSL verification disabled for HuggingFace downloads")


# Apply the patch when this module is imported
disable_ssl_verification()
