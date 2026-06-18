"""Strategy implementations: S1-S4 plus benchmarks.

Each strategy maps a decision date + market context to a target weight vector.
S4 (target-vol) is an overlay derived from S3's realised return path.
"""
from .all_weather import AllWeather  # noqa: F401
from .base import Context, Strategy  # noqa: F401
from .benchmarks import EqualWeight, BuyHold  # noqa: F401
from .rotation import Rotation  # noqa: F401
from .style_rotation import StyleRotation  # noqa: F401
from .target_vol import target_vol_overlay  # noqa: F401
