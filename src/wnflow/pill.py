"""Floating Pill-Window unten am Bildschirm.

v0.2.0 — Wispr-Flow-Style visual feedback.

Architektur (rev3 Spec):
- Lazy NSWindow-Creation: __init__ läuft schnell (~10ms),
  NSWindow erst bei erstem show() (~100-200ms)
- 4 States: hidden / recording / loading / done
- Waveform: sqrt(rms) * 50 clamped 4-24px (rev3 N3-Fix)
- Mode-Indicator: kleiner Punkt rechts (none/blau/rot)

WICHTIG Threading:
- ALLE Methoden müssen vom Main-Thread aufgerufen werden
- assert_main_thread() in jeder public Methode
- update_level kann hochfrequent (50Hz) gerufen werden
"""

import logging
import math
from enum import Enum
from pathlib import Path

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSImage,
    NSRect,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowStyleMaskBorderless,
)
from Foundation import NSObject  # type: ignore[import-not-found]

from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)


PILL_WIDTH = 140
PILL_HEIGHT = 36
PILL_BOTTOM_MARGIN = 24
BAR_COUNT = 5
BAR_WIDTH = 3
BAR_SPACING = 2
BAR_HEIGHT_MAX = 24
BAR_HEIGHT_MIN = 4

MODE_COLORS = {
    "verbatim": None,  # kein Punkt
    "formal": (0.231, 0.510, 0.965, 1.0),  # #3b82f6
    "rage": (0.937, 0.267, 0.267, 1.0),  # #ef4444
}


class PillState(Enum):
    HIDDEN = "hidden"
    RECORDING = "recording"
    LOADING = "loading"
    DONE = "done"


class PillView(NSView):
    """Custom-Drawing NSView für die Pill."""

    def initWithFrame_(self, frame):
        self = objc.super(PillView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._level = 0.0
        self._state = PillState.HIDDEN
        self._mode = "verbatim"
        return self

    def setLevel_(self, level):
        self._level = level
        self.setNeedsDisplay_(True)

    def setStateValue_(self, state):
        self._state = state
        self.setNeedsDisplay_(True)

    def setMode_(self, mode):
        self._mode = mode
        self.setNeedsDisplay_(True)

    def drawRect_(self, dirty_rect):
        # Background: schwarz mit Alpha 0.8
        NSColor.colorWithCalibratedWhite_alpha_(0.1, 0.8).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 18, 18
        )
        path.fill()

        if self._state == PillState.RECORDING:
            self._draw_waveform()
        elif self._state == PillState.LOADING:
            self._draw_loading()
        elif self._state == PillState.DONE:
            self._draw_done()

        self._draw_mode_indicator()

    def _draw_waveform(self):
        """sqrt-Skalierung (rev3 N3-Fix)."""
        bar_height = max(
            BAR_HEIGHT_MIN,
            min(BAR_HEIGHT_MAX, int(math.sqrt(max(0.0, self._level)) * 50)),
        )

        total_width = BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_SPACING
        start_x = (self.bounds().size.width - total_width) / 2
        center_y = self.bounds().size.height / 2

        NSColor.whiteColor().set()
        for i in range(BAR_COUNT):
            x = start_x + i * (BAR_WIDTH + BAR_SPACING)
            distance_from_center = abs(i - (BAR_COUNT - 1) / 2)
            scale = 1.0 - (distance_from_center * 0.15)
            h = bar_height * scale
            rect = NSRect((x, center_y - h / 2), (BAR_WIDTH, h))
            bar = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 1.5, 1.5)
            bar.fill()

    def _draw_loading(self):
        """Loading-State: 3 pulsing dots in Pill-Mitte."""
        NSColor.whiteColor().set()
        center_x = self.bounds().size.width / 2
        center_y = self.bounds().size.height / 2
        dot_size = 4
        for i in range(3):
            x = center_x - 12 + i * 8
            rect = NSRect((x, center_y - dot_size / 2), (dot_size, dot_size))
            dot = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                rect, 2, 2
            )
            dot.fill()

    def _draw_done(self):
        """Done-State: Häkchen via abgewinkelte Linie."""
        NSColor.whiteColor().set()
        center_x = self.bounds().size.width / 2
        center_y = self.bounds().size.height / 2
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((center_x - 8, center_y))
        path.lineToPoint_((center_x - 2, center_y - 6))
        path.lineToPoint_((center_x + 8, center_y + 6))
        path.setLineWidth_(2.0)
        path.stroke()

    def _draw_mode_indicator(self):
        """Mode-Indicator-Punkt rechts in Pill."""
        color = MODE_COLORS.get(self._mode)
        if color is None:
            return
        NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        x = self.bounds().size.width - 12
        y = self.bounds().size.height / 2 - 3
        rect = NSRect((x, y), (6, 6))
        dot = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, 3, 3)
        dot.fill()


class PillWindow:
    """Wrapper um NSWindow + PillView mit Lazy-Creation."""

    def __init__(self) -> None:
        # rev3 S-new-2: Lazy NSWindow-Creation.
        # __init__ läuft schnell — NSWindow erst bei erstem show().
        self._window = None
        self._view = None
        self._state = PillState.HIDDEN
        self._mode = "verbatim"
        self.is_ready = False

    def _ensure_window(self) -> None:
        """Lazy-Init der NSWindow + NSView. Nur beim ersten show() aufgerufen."""
        if self._window is not None:
            return
        screen_frame = NSScreen.mainScreen().frame()
        x = (screen_frame.size.width - PILL_WIDTH) / 2
        y = PILL_BOTTOM_MARGIN
        window_frame = NSRect((x, y), (PILL_WIDTH, PILL_HEIGHT))

        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            window_frame,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(NSStatusWindowLevel)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setOpaque_(False)
        self._window.setIgnoresMouseEvents_(True)
        self._window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
        )

        self._view = PillView.alloc().initWithFrame_(
            NSRect((0, 0), (PILL_WIDTH, PILL_HEIGHT))
        )
        self._window.setContentView_(self._view)
        self.is_ready = True
        log.info("PillWindow ready (lazy-init)")

    def show(self, state: PillState, mode: str = "verbatim") -> None:
        assert_main_thread("PillWindow.show")
        try:
            self._ensure_window()
            self._state = state
            self._mode = mode
            self._view.setMode_(mode)
            self._view.setStateValue_(state)
            self._window.orderFront_(None)
        except Exception:
            log.exception("PillWindow.show failed")

    def update_state(self, state: PillState) -> None:
        assert_main_thread("PillWindow.update_state")
        if not self.is_ready:
            return
        try:
            self._state = state
            self._view.setStateValue_(state)
        except Exception:
            log.exception("PillWindow.update_state failed")

    def update_mode(self, mode: str) -> None:
        """Für S3-Fix: Pre-Show Mode-Color bei mode_hint event.

        rev2 S1-Fix: triggert _ensure_window() damit der Mode-Indicator
        beim allerersten Recording sofort wirkt (sonst no-op wegen is_ready=False).
        Wir orderFront NICHT — Window bleibt hidden bis show() es ordnen.
        """
        assert_main_thread("PillWindow.update_mode")
        try:
            self._ensure_window()  # rev2 S1-Fix: lazy-init triggern
            self._mode = mode
            self._view.setMode_(mode)
        except Exception:
            log.exception("PillWindow.update_mode failed")

    def update_level(self, level: float) -> None:
        """Wird 50Hz gerufen. Kein assert (Hot-Path)."""
        if not self.is_ready:
            return
        try:
            self._view.setLevel_(level)
        except Exception:
            log.exception("PillWindow.update_level failed")

    def hide(self) -> None:
        assert_main_thread("PillWindow.hide")
        if not self.is_ready or self._window is None:
            return
        try:
            self._state = PillState.HIDDEN
            self._window.orderOut_(None)
        except Exception:
            log.exception("PillWindow.hide failed")
