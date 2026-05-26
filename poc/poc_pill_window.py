"""POC: NSWindow Pill unten mittig mit animierter Waveform.

Validiert die kritischen Pill-Annahmen aus Spec v0.2.0 §10:
- NSWindow + Borderless + StatusWindowLevel + transparenter Background
- ignoresMouseEvents (Mausklicks gehen durch)
- 50Hz setNeedsDisplay ohne Stottern
- Bleibt sichtbar in Vollbild-Apps (NSWindowCollectionBehaviorCanJoinAllSpaces)
- NSTimer in NSRunLoopCommonModes (kein Stottern bei offenen Menüs)

Manuell durchspielen, dann Strg+C im Terminal.
"""

import math
import time

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSApplication,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSRect,
    NSScreen,
    NSStatusWindowLevel,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowStyleMaskBorderless,
)
from Foundation import (  # type: ignore[import-not-found]
    NSObject,
    NSRunLoop,
    NSRunLoopCommonModes,
    NSTimer,
)
from PyObjCTools import AppHelper  # type: ignore[import-not-found]

PILL_WIDTH = 140
PILL_HEIGHT = 36
PILL_BOTTOM_MARGIN = 24
BAR_COUNT = 5
BAR_WIDTH = 3
BAR_SPACING = 2
POLL_INTERVAL = 0.02  # 20ms = 50Hz


class WaveformView(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(WaveformView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._level = 0.0
        self._frame_count = 0
        return self

    def setLevel_(self, level):
        self._level = level
        self.setNeedsDisplay_(True)

    def drawRect_(self, dirty_rect):
        # Background: schwarz mit Alpha 0.8
        NSColor.colorWithCalibratedWhite_alpha_(0.1, 0.8).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), 18, 18
        )
        path.fill()

        # Waveform-Balken — sqrt-Skala (rev3 N3-Fix aus Spec)
        bar_height_max = 24
        bar_height = max(4, min(bar_height_max, int(math.sqrt(self._level) * 50)))

        # Mittlere X-Position der 5 Balken
        total_width = BAR_COUNT * BAR_WIDTH + (BAR_COUNT - 1) * BAR_SPACING
        start_x = (self.bounds().size.width - total_width) / 2
        center_y = self.bounds().size.height / 2

        NSColor.whiteColor().set()
        for i in range(BAR_COUNT):
            x = start_x + i * (BAR_WIDTH + BAR_SPACING)
            # Mittlerer Balken am höchsten, außen kleiner
            distance_from_center = abs(i - (BAR_COUNT - 1) / 2)
            scale = 1.0 - (distance_from_center * 0.15)
            h = bar_height * scale
            rect = NSRect((x, center_y - h / 2), (BAR_WIDTH, h))
            bar = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                rect, 1.5, 1.5
            )
            bar.fill()


class PocApp(NSObject):
    def init(self):
        self = objc.super(PocApp, self).init()
        if self is None:
            return None
        self._frame_count = 0
        self._start_time = time.perf_counter()
        return self

    def setup(self):
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

        self._view = WaveformView.alloc().initWithFrame_(
            NSRect((0, 0), (PILL_WIDTH, PILL_HEIGHT))
        )
        self._window.setContentView_(self._view)
        self._window.orderFront_(None)

        # NSTimer in CommonModes (B2-Fix aus Spec)
        timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            POLL_INTERVAL, self, "tick:", None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)
        self._timer = timer  # strong-ref defensive

        print(f"PocApp ready. Window: {PILL_WIDTH}x{PILL_HEIGHT}")
        print("Manuell testen:")
        print("  1. Pille sichtbar unten mittig?")
        print("  2. Ueber andere Apps sichtbar?")
        print("  3. In Vollbild-App sichtbar? (Safari Strg+Cmd+F)")
        print("  4. Mausklick durch Pille auf Notes funktioniert?")
        print("  5. Stottern bei offenem Apple-Menue?")
        print()
        print("Strg+C im Terminal zum Beenden.")

    def tick_(self, _timer):
        # Simuliere RMS mit Sinus
        self._frame_count += 1
        t = time.perf_counter() - self._start_time
        # Variiere zwischen 0.0 und 0.3 (realistischer RMS-Bereich)
        simulated_rms = 0.15 + 0.15 * math.sin(t * 3)
        self._view.setLevel_(simulated_rms)

        # FPS-Report alle 5s
        if self._frame_count % 250 == 0:
            elapsed = t
            fps = self._frame_count / elapsed
            print(f"  FPS gemessen: {fps:.1f}")


def main():
    app = NSApplication.sharedApplication()
    poc = PocApp.alloc().init()
    poc.setup()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
