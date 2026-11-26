"""dor — CLI de imersão em romeno para falantes de português."""

import os

# pygame cospe um banner de boas-vindas no import; precisa ser silenciado antes.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

__version__ = "0.1.0"
