"""linkforge — short links with click analytics."""
from .core import Click, Link, LinkStore, classify_referrer, detect_device, validate_target

__all__ = ["Click", "Link", "LinkStore", "classify_referrer",
           "detect_device", "validate_target"]
__version__ = "1.0.0"
