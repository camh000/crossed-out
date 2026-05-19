import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import MagicMock

# Block real pygame from being imported
class MockPygame:
    def __getattr__(self, name):
        attr = MagicMock()
        if name == 'init':
            attr.return_value = (1, 0)
        elif name == 'QUIT':
            return 0
        elif name == 'display':
            disp = MagicMock()
            disp.init.return_value = None
            disp.set_mode.return_value = MagicMock()
            disp.set_caption.return_value = None
            disp.get_surface.return_value = MagicMock()
            disp.flip.return_value = None
            return disp
        elif name == 'font':
            font = MockFont()
            font.SysFont.return_value = MagicMock()
            return font
        elif name == 'time':
            t = MagicMock()
            t.get_ticks.return_value = 0
            return t
        elif name == 'event':
            ev = MagicMock()
            ev.quit = 12
            return ev
        elif name == 'KEYDOWN':
            return 768
        elif name == 'K_p':
            return 112
        elif name == 'K_r':
            return 114
        elif name == 'K_w':
            return 119
        elif name == 'K_a':
            return 97
        elif name == 'K_s':
            return 115
        elif name == 'K_d':
            return 100
        elif name == 'K_SPACE':
            return 32
        elif name == 'K_RETURN':
            return 257
        elif name == 'HWSURFACE':
            return 65536
        elif name == 'DOUBLEBUF':
            return 1
        else:
            return attr
    def __call__(self, *a, **kw):
        return MagicMock()

class MockDisplay:
    def set_mode(self, *a, **kw):
        return MagicMock()
    def set_caption(self, *a, **kw):
        return None
    def get_surface(self):
        return MagicMock()
    def flip(self):
        return None
    def init(self):
        return None

class MockFont:
    @staticmethod
    def SysFont(*a, **kw):
        f = MagicMock()
        r = MagicMock()
        r.get_width.return_value = 0
        r.get_height.return_value = 0
        f.render.return_value = r
        return f

sys.modules['pygame'] = MockPygame()
sys.modules['pygame.display'] = MagicMock()
sys.modules['pygame.font'] = MagicMock()
sys.modules['pygame.time'] = MagicMock()
sys.modules['pygame.event'] = MagicMock()
