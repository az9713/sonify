from .base import Lens, ControlState
from .atmosphere import AtmosphereLens
from .pulse import PulseLens
from .lattice import LatticeLens
from .flow import FlowLens

LENSES: dict[str, type[Lens]] = {
    "atmosphere": AtmosphereLens,
    "pulse": PulseLens,
    "lattice": LatticeLens,
    "flow": FlowLens,
}
