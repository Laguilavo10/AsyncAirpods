"""Adapters that implement the application ports with concrete libraries."""

import sys

# comtypes initializes COM when first imported; it must join the multithreaded
# apartment, because bleak's WinRT callbacks never fire on a single-threaded
# apartment without a window message loop. This must run before any comtypes import.
sys.coinit_flags = 0  # COINIT_MULTITHREADED
