"""POC 1: rumps Menubar-App im PyInstaller-Bundle.

Validiert dass rumps + PyInstaller zusammen funktionieren.
Erfolg = Menubar-Icon erscheint, Click+Notification funktionieren.
"""

import rumps


class HelloApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("POC1", quit_button="Quit")

    @rumps.clicked("Hello")
    def hello(self, _) -> None:
        rumps.notification("POC 1", "rumps funktioniert", "im PyInstaller-Bundle")


if __name__ == "__main__":
    # PyInstaller-Bundle-Fix: freeze_support gegen fork-loop
    import multiprocessing
    multiprocessing.freeze_support()
    HelloApp().run()
