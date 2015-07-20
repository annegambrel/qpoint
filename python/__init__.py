"""qpoint

A lightweight library for efficient pointing.

Based on M. Nolta's libactpol.
Uses the SOFA Software Collection, available from http://www.iausofa.org/
"""

__version__ = (1, 4, 1)

def version():
    return __version__

import tools
from qpoint_class import *
from qmap_class import *
