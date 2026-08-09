"""Console singleton de Rich. Todos los modulos importan `console` desde aqui.

En Windows se habilita previamente ENABLE_VIRTUAL_TERMINAL_PROCESSING para que
Rich no use el renderer Win32 legacy (superpone texto en PowerShell 5.1 / conhost
clasico). Una vez habilitado, Rich autodetecta VT y elige bien tipo de color y
renderizado. No se fuerza terminal: si la salida esta redirigida a un archivo,
Rich se comporta normal y no rompe los spinners/texto de sugerencias.
"""
import os

from rich.console import Console


def _enable_windows_vt():
    """Habilita ENABLE_VIRTUAL_TERMINAL_PROCESSING en stdout y stderr."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            if handle in (0, -1):
                continue
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


_enable_windows_vt()
console = Console()
