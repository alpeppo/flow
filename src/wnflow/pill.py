"""Floating Pill-Window unten am Bildschirm.

v0.3.0 — Diktat-HUD-Style (long waveform + live timer + cancel-button).

Layout:
  [red dot]  [scrolling waveform-bars]  |  [0:07]  [✕]

States:
- HIDDEN   — Window orderedOut
- RECORDING — Roter Dot + Waveform + Timer + X
- LOADING  — 3 pulsing dots (during STT/post)
- DONE     — Checkmark (Erfolg)

WICHTIG Threading:
- ALLE Methoden müssen vom Main-Thread aufgerufen werden
- update_level / set_elapsed können hochfrequent (50Hz / 10Hz) gerufen werden
- assert_main_thread() in jeder public Methode ausser hot-paths

Klick-Verhalten:
- NonactivatingPanel klaut keinen Focus.
- setIgnoresMouseEvents_(False) damit X-Button klickbar ist.
"""

import logging
import math
import time
import traceback
from collections import deque
from enum import Enum

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSFont,
    NSPanel,
    NSPoint,
    NSRect,
    NSScreen,
    NSScreenSaverWindowLevel,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import (  # type: ignore[import-not-found]
    NSAttributedString,
    NSDictionary,
    NSMutableDictionary,
    NSObject,
)

def _monospace_font(size: float):
    """Robuste Font-Aufloesung. Modern API mit Fallback."""
    try:
        return NSFont.monospacedDigitSystemFontOfSize_weight_(size, 0.0)
    except Exception:
        try:
            return NSFont.userFixedPitchFontOfSize_(size)
        except Exception:
            return NSFont.systemFontOfSize_(size)

from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)


PILL_WIDTH = 260
PILL_HEIGHT = 36
PILL_BOTTOM_MARGIN = 28
PILL_RADIUS = PILL_HEIGHT / 2

# Layout — von links nach rechts mit klaren Boxes:
# [LP][RedDot][gap][Waveform][gap][Timer][gap][X][RP]
LEFT_PAD = 10
DOT_RADIUS = 4
GAP_DOT_WAVE = 6
GAP_WAVE_TIMER = 12
TIMER_WIDTH = 36          # reicht für "00:00" mono13
GAP_TIMER_X = 10
CANCEL_RADIUS = 9
RIGHT_PAD = 10

# Waveform
BAR_WIDTH = 1.8
BAR_GAP = 1.8
BAR_HEIGHT_MIN = 2
BAR_HEIGHT_MAX = 22
BAR_HISTORY = 48

# Pulse-Animation rate (LOADING dots)
LOADING_DOT_RADIUS = 3.0

MODE_COLORS = {
    "verbatim": None,  # kein Indicator
    "formal": (0.231, 0.510, 0.965, 1.0),
    "rage": (0.937, 0.267, 0.267, 1.0),
}


class PillState(Enum):
    HIDDEN = "hidden"
    RECORDING = "recording"
    LOADING = "loading"
    DONE = "done"


class PillView(NSView):
    """Custom-Drawing NSView für die Pill mit Hit-Testing für X-Button."""

    def initWithFrame_(self, frame):
        self = objc.super(PillView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._level = 0.0
        self._level_history: deque = deque([0.0] * BAR_HISTORY, maxlen=BAR_HISTORY)
        self._state = PillState.HIDDEN
        self._mode = "verbatim"
        self._elapsed_s = 0.0
        self._cancel_callback = None
        self._cancel_hover = False
        self._tracking_area = None
        return self

    def updateTrackingAreas(self):
        """Tracking-Area neu anlegen damit mouseMoved_/mouseExited_ feuern."""
        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSTrackingActiveAlways,
                NSTrackingArea,
                NSTrackingInVisibleRect,
                NSTrackingMouseEnteredAndExited,
                NSTrackingMouseMoved,
            )
            if self._tracking_area is not None:
                self.removeTrackingArea_(self._tracking_area)
            options = (
                NSTrackingMouseEnteredAndExited
                | NSTrackingMouseMoved
                | NSTrackingActiveAlways
                | NSTrackingInVisibleRect
            )
            self._tracking_area = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(), options, self, None
            )
            self.addTrackingArea_(self._tracking_area)
        except Exception:
            log.exception("updateTrackingAreas failed")
        objc.super(PillView, self).updateTrackingAreas()

    # ---------- Setter -------------------------------------------------------

    def pushLevel_(self, level):
        """50Hz Hot-Path. Schiebt Wert in History und triggert Redraw."""
        self._level = float(level)
        self._level_history.append(self._level)
        self.setNeedsDisplay_(True)

    def setStateValue_(self, state):
        self._state = state
        if state != PillState.RECORDING:
            self._level_history = deque([0.0] * BAR_HISTORY, maxlen=BAR_HISTORY)
        self.setNeedsDisplay_(True)

    def setMode_(self, mode):
        self._mode = mode
        self.setNeedsDisplay_(True)

    def setElapsed_(self, seconds):
        self._elapsed_s = float(seconds)
        self.setNeedsDisplay_(True)

    def setCancelCallback_(self, cb):
        self._cancel_callback = cb

    # ---------- Mouse --------------------------------------------------------

    def _cancel_button_rect(self):
        """Returns NSRect-Tuple ((x,y),(w,h)) — wir nutzen es direkt für Drawing."""
        cx, cy = self._x_button_center()
        return NSRect((cx - CANCEL_RADIUS, cy - CANCEL_RADIUS),
                      (CANCEL_RADIUS * 2, CANCEL_RADIUS * 2))

    def _point_in_cancel(self, point) -> bool:
        cx, cy = self._x_button_center()
        try:
            px, py = float(point.x), float(point.y)
        except AttributeError:
            px, py = float(point[0]), float(point[1])
        dx = px - cx
        dy = py - cy
        return (dx * dx + dy * dy) <= (CANCEL_RADIUS * CANCEL_RADIUS)

    def mouseDown_(self, event):
        try:
            if self._state != PillState.RECORDING:
                return
            loc = self.convertPoint_fromView_(event.locationInWindow(), None)
            if self._point_in_cancel(loc) and self._cancel_callback is not None:
                self._cancel_callback()
        except Exception:
            log.exception("PillView.mouseDown_ failed")

    def mouseMoved_(self, event):
        try:
            loc = self.convertPoint_fromView_(event.locationInWindow(), None)
            hover = self._point_in_cancel(loc)
            if hover != self._cancel_hover:
                self._cancel_hover = hover
                self.setNeedsDisplay_(True)
        except Exception:
            log.exception("PillView.mouseMoved_ failed")

    def mouseExited_(self, event):
        try:
            if self._cancel_hover:
                self._cancel_hover = False
                self.setNeedsDisplay_(True)
        except Exception:
            log.exception("PillView.mouseExited_ failed")

    def acceptsFirstMouse_(self, event):
        return True

    # ---------- Drawing ------------------------------------------------------

    def drawRect_(self, dirty_rect):
        # Hart-defensiv: PyObjC wandelt jede Python-Exception hier in eine
        # NSException → App-Crash (EXC_BREAKPOINT). Wir fangen alles ab
        # und loggen den Traceback, damit Pill-Fehler nie die App killen.
        try:
            self._draw_safe()
        except Exception:
            log.error("PillView.drawRect_ crashed:\n%s", traceback.format_exc())

    def _draw_safe(self):
        w, h = self._bounds_size()
        # Background: very dark, slight transparency
        try:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.078, 0.078, 0.086, 0.95).set()
            bg_rect = NSRect((0.0, 0.0), (w, h))
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                bg_rect, PILL_RADIUS, PILL_RADIUS
            )
            path.fill()
        except Exception:
            log.exception("Pill background draw failed")

        if self._state == PillState.RECORDING:
            self._safe_call(self._draw_red_dot, "red_dot")
            self._safe_call(self._draw_waveform, "waveform")
            self._safe_call(self._draw_timer, "timer")
            self._safe_call(self._draw_cancel_button, "cancel_btn")
        elif self._state == PillState.LOADING:
            self._safe_call(self._draw_loading, "loading")
        elif self._state == PillState.DONE:
            self._safe_call(self._draw_done, "done")

        self._safe_call(self._draw_mode_indicator, "mode_indicator")

    def _safe_call(self, fn, label):
        try:
            fn()
        except Exception:
            log.error("Pill draw %s failed:\n%s", label, traceback.format_exc())

    # Layout-Helper -----------------------------------------------------------

    def _bounds_size(self):
        """Returns (width, height) als float-Tuple. Robust gegen PyObjC-Bridging."""
        b = self.bounds()
        try:
            return float(b.size.width), float(b.size.height)
        except AttributeError:
            # Bundle-Fallback: bounds() ist als ((x,y),(w,h)) zurueckgegeben.
            (_, _), (w, h) = b
            return float(w), float(h)

    def _x_button_center(self):
        w, h = self._bounds_size()
        cx = w - RIGHT_PAD - CANCEL_RADIUS
        cy = h / 2.0
        return cx, cy

    def _timer_box(self):
        """Returns (x, y, width, height) als Tuple."""
        w, h = self._bounds_size()
        x_right_edge_of_timer = w - RIGHT_PAD - (2 * CANCEL_RADIUS) - GAP_TIMER_X
        return (x_right_edge_of_timer - TIMER_WIDTH, 0.0, float(TIMER_WIDTH), h)

    def _wave_box(self):
        """Returns (x, y, width, height) als Tuple."""
        w, h = self._bounds_size()
        timer_x, _, _, _ = self._timer_box()
        x_left = LEFT_PAD + (2 * DOT_RADIUS) + GAP_DOT_WAVE
        x_right = timer_x - GAP_WAVE_TIMER
        return (float(x_left), 0.0, max(0.0, x_right - x_left), h)

    # Zeichnungen -------------------------------------------------------------

    def _draw_red_dot(self):
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.937, 0.267, 0.267, 1.0).set()
        _, h = self._bounds_size()
        cy = h / 2.0
        rect = NSRect(
            (LEFT_PAD, cy - DOT_RADIUS),
            (DOT_RADIUS * 2, DOT_RADIUS * 2),
        )
        NSBezierPath.bezierPathWithOvalInRect_(rect).fill()

    def _draw_waveform(self):
        wx, _, ww, wh = self._wave_box()
        if ww <= 0:
            return
        step = BAR_WIDTH + BAR_GAP
        max_bars = max(1, int(ww / step))
        values = list(self._level_history)[-max_bars:]
        if not values:
            return

        now = time.perf_counter()
        idle_pulse = (math.sin(now * 4.0) + 1.0) / 2.0 * 0.04

        NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.85).set()
        cy = wh / 2.0
        wave_right = wx + ww
        for i, lvl in enumerate(reversed(values)):
            effective = max(0.0, lvl) + idle_pulse * 0.5
            h = max(
                BAR_HEIGHT_MIN,
                min(BAR_HEIGHT_MAX, math.sqrt(effective) * 70.0),
            )
            x = wave_right - (i + 1) * step + BAR_GAP / 2
            if x < wx:
                break
            rect = NSRect((x, cy - h / 2), (BAR_WIDTH, h))
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                rect, BAR_WIDTH / 2, BAR_WIDTH / 2
            ).fill()

    def _draw_timer(self):
        mm = int(self._elapsed_s) // 60
        ss = int(self._elapsed_s) % 60
        text = f"{mm}:{ss:02d}"
        font = _monospace_font(12.0)
        color = NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.92)
        attrs = NSMutableDictionary.dictionary()
        attrs.setObject_forKey_(font, "NSFont")
        attrs.setObject_forKey_(color, "NSColor")
        attr_text = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
        ts = attr_text.size()
        try:
            tw, th = float(ts.width), float(ts.height)
        except AttributeError:
            tw, th = float(ts[0]), float(ts[1])
        tx, _, tw_box, th_box = self._timer_box()
        x = tx + tw_box - tw
        y = (th_box - th) / 2.0
        attr_text.drawAtPoint_(NSPoint(x, y))

    def _draw_cancel_button(self):
        cx, cy = self._x_button_center()
        rect = NSRect(
            (cx - CANCEL_RADIUS, cy - CANCEL_RADIUS),
            (CANCEL_RADIUS * 2, CANCEL_RADIUS * 2),
        )

        # Hintergrund-Circle: deutlich sichtbar, bei Hover heller.
        bg_alpha = 0.30 if self._cancel_hover else 0.18
        NSColor.colorWithCalibratedWhite_alpha_(1.0, bg_alpha).set()
        NSBezierPath.bezierPathWithOvalInRect_(rect).fill()

        # X-Glyphe: weiss, dick genug um auf dunklem Bg zu lesen.
        NSColor.whiteColor().set()
        path = NSBezierPath.bezierPath()
        arm = 4.0
        path.moveToPoint_((cx - arm, cy - arm))
        path.lineToPoint_((cx + arm, cy + arm))
        path.moveToPoint_((cx - arm, cy + arm))
        path.lineToPoint_((cx + arm, cy - arm))
        path.setLineWidth_(2.0)
        try:
            path.setLineCapStyle_(1)  # NSLineCapStyleRound
        except Exception:
            pass
        path.stroke()

    def _draw_loading(self):
        NSColor.whiteColor().set()
        w, h = self._bounds_size()
        cy = h / 2.0
        cx = w / 2.0
        now = time.perf_counter()
        for i in range(3):
            phase = (now * 2.2 + i * 0.35) % 1.0
            scale = 0.55 + 0.45 * abs(math.sin(phase * math.pi))
            r = LOADING_DOT_RADIUS * scale
            x = cx - 14 + i * 14
            rect = NSRect((x - r, cy - r), (r * 2, r * 2))
            NSBezierPath.bezierPathWithOvalInRect_(rect).fill()

    def _draw_done(self):
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.255, 0.776, 0.388, 1.0).set()
        w, h = self._bounds_size()
        cx = w / 2.0
        cy = h / 2.0
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((cx - 10, cy))
        path.lineToPoint_((cx - 3, cy - 7))
        path.lineToPoint_((cx + 11, cy + 7))
        path.setLineWidth_(2.4)
        try:
            path.setLineCapStyle_(1)
            path.setLineJoinStyle_(1)
        except Exception:
            pass
        path.stroke()

    def _draw_mode_indicator(self):
        color = MODE_COLORS.get(self._mode)
        if color is None:
            return
        NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        _, h = self._bounds_size()
        x = LEFT_PAD - 3
        y = h - 8
        rect = NSRect((x, y), (5, 5))
        NSBezierPath.bezierPathWithOvalInRect_(rect).fill()


class PillWindow:
    """Wrapper um NSWindow + PillView mit Lazy-Creation."""

    def __init__(self) -> None:
        self._window = None
        self._view = None
        self._state = PillState.HIDDEN
        self._mode = "verbatim"
        self._cancel_callback = None
        self.is_ready = False

    def _ensure_window(self) -> None:
        if self._window is not None:
            return
        screen_frame = NSScreen.mainScreen().frame()
        x = (screen_frame.size.width - PILL_WIDTH) / 2
        y = PILL_BOTTOM_MARGIN
        window_frame = NSRect((x, y), (PILL_WIDTH, PILL_HEIGHT))

        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            window_frame,
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setLevel_(NSScreenSaverWindowLevel)
        self._window.setBackgroundColor_(NSColor.clearColor())
        self._window.setOpaque_(False)
        # WICHTIG: jetzt klickbar für X-Button. NonactivatingPanel verhindert Focus-Steal.
        self._window.setIgnoresMouseEvents_(False)
        self._window.setFloatingPanel_(True)
        self._window.setHidesOnDeactivate_(False)
        self._window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )

        self._view = PillView.alloc().initWithFrame_(
            NSRect((0, 0), (PILL_WIDTH, PILL_HEIGHT))
        )
        self._window.setContentView_(self._view)
        if self._cancel_callback is not None:
            self._view.setCancelCallback_(self._cancel_callback)
        self.is_ready = True
        log.info("PillWindow ready (lazy-init, %dx%d)", PILL_WIDTH, PILL_HEIGHT)

    def set_cancel_callback(self, cb) -> None:
        """Speichert Cancel-Callback. Wird beim X-Klick aufgerufen."""
        self._cancel_callback = cb
        if self.is_ready and self._view is not None:
            self._view.setCancelCallback_(cb)

    def show(self, state: PillState, mode: str = "verbatim") -> None:
        assert_main_thread("PillWindow.show")
        try:
            self._ensure_window()
            self._state = state
            self._mode = mode
            self._view.setMode_(mode)
            self._view.setElapsed_(0.0)
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
        assert_main_thread("PillWindow.update_mode")
        try:
            self._ensure_window()
            self._mode = mode
            self._view.setMode_(mode)
        except Exception:
            log.exception("PillWindow.update_mode failed")

    def update_level(self, level: float) -> None:
        """50Hz hot-path. Kein assert."""
        if not self.is_ready:
            return
        try:
            self._view.pushLevel_(level)
        except Exception:
            log.exception("PillWindow.update_level failed")

    def set_elapsed(self, seconds: float) -> None:
        """10Hz timer-update. Kein assert."""
        if not self.is_ready:
            return
        try:
            self._view.setElapsed_(seconds)
        except Exception:
            log.exception("PillWindow.set_elapsed failed")

    def hide(self) -> None:
        assert_main_thread("PillWindow.hide")
        if not self.is_ready or self._window is None:
            return
        try:
            self._state = PillState.HIDDEN
            self._window.orderOut_(None)
        except Exception:
            log.exception("PillWindow.hide failed")
