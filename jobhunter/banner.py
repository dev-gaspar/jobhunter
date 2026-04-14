"""Render del banner de JobHunter segun ancho del terminal."""
import shutil

from jobhunter.constants import BANNER_LARGE, BANNER_SMALL, VERSION


def get_banner():
    width = shutil.get_terminal_size((80, 24)).columns
    b = BANNER_LARGE if width >= 76 else BANNER_SMALL
    return b.format(version=VERSION)
