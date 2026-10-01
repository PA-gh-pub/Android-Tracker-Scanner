"""UI components for the scanner — ported from the main tool.

Every widget reads colors from core.theme.THEME, which mirrors the
website's design tokens exactly, so tool and site share one visual
identity. Light theme only (deliberately minimal).
"""

import tkinter as tk

from core.theme import THEME

_t = THEME

class Card(tk.Frame):
    """A panel with a subtle border."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=_t['bg_white'],
            highlightbackground=_t['border_color'],
            highlightthickness=1,
            **kwargs
        )

class GradientBanner(tk.Canvas):
    """Vertical-gradient hero banner with title and subtitle.

    Drawn as BAND-pixel rectangles instead of per-pixel lines, so
    window resizing stays smooth even on large banners.
    """

    BAND = 2   # pixels per gradient band

    def __init__(self, parent, title, subtitle, height=110):
        super().__init__(parent, height=height,
                         highlightthickness=0, bd=0)
        self._title = title
        self._subtitle = subtitle
        self.bind('<Configure>', lambda e: self.redraw())
        self.redraw()

    @staticmethod
    def _hex_to_rgb(hx):
        hx = hx.lstrip('#')
        return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _lerp(c1, c2, t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

    def _mix(self, c1, c2, t):
        r, g, b = self._lerp(c1, c2, t)
        return f'#{r:02x}{g:02x}{b:02x}'

    def redraw(self):
        self.delete('all')
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)

        c1 = self._hex_to_rgb(_t['bg_gradient_start'])
        c2 = self._hex_to_rgb(_t['bg_gradient_end'])
        for y in range(0, h, self.BAND):
            frac = y / max(h - 1, 1)
            self.create_rectangle(
                0, y, w, min(y + self.BAND, h),
                outline='', fill=self._mix(c1, c2, frac))

        a1 = self._hex_to_rgb(_t['accent_blue'])
        a2 = self._hex_to_rgb(_t['accent_purple'])
        for x in range(0, w, self.BAND):
            frac = x / max(w - 1, 1)
            self.create_rectangle(
                x, h - 4, min(x + self.BAND, w), h,
                outline='', fill=self._mix(a1, a2, frac))

        self.create_text(
            24, h // 2 - 16, text=self._title, anchor='w',
            font=('Helvetica', 18, 'bold'),
            fill=_t['primary_dark'])
        self.create_text(
            24, h // 2 + 10, text=self._subtitle, anchor='w',
            font=('Helvetica', 10),
            fill=_t['text_medium'])

class ThemedButton(tk.Button):
    """Primary accent button — a classic tk.Button, deliberately.

    ttk.Button delegates its drawing to a Linux theme engine that
    fails to repaint on window maximize (bottom-of-window buttons
    render blank until hovered). A classic tk.Button draws itself,
    so it repaints reliably.
    """

    def __init__(self, parent, **kwargs):
        defaults = {
            'bg': _t['accent_blue'],
            'fg': 'white',
            'activebackground': _t['accent_hover'],
            'activeforeground': 'white',
            'relief': 'flat', 'bd': 0,
            'highlightthickness': 0,
            'cursor': 'hand2',
            'font': ('Helvetica', 11, 'bold'),
            'padx': 24, 'pady': 10,
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)

class LogText(tk.Text):
    """Monospace log area with colored tags.

    Tag colors: success / error / info / detail. Colors are fixed
    (no theme switch), so they're configured once here.
    """

    def __init__(self, parent, **kwargs):
        defaults = {
            'bg': _t['terminal_bg'],
            'fg': _t['terminal_fg'],
            'font': ('Monospace', 10),
            'insertbackground': _t['primary_blue'],
            'borderwidth': 0, 'highlightthickness': 0,
            'wrap': 'word', 'padx': 12, 'pady': 8,
            'state': 'disabled',
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)
        self.tag_configure('phase', foreground=_t['primary_blue'],
                            font=('Monospace', 10, 'bold'))
        self.tag_configure('detail', foreground=_t['terminal_fg'])
        self.tag_configure('success', foreground=_t['success'])
        self.tag_configure('error', foreground=_t['error'])

    def append(self, text, tag='detail'):
        """Thread-safe append: disable→insert→enable→scroll."""
        self.configure(state='normal')
        self.insert('end', text + '\n', tag)
        self.see('end')
        self.configure(state='disabled')
