"""Command-Detection: erkennt Trigger-Wörter am Anfang von STT-Output.

Wenn ein Trigger erkannt wird, wechselt die Pipeline in Command-Mode:
- STT-Text wird als Instruktion interpretiert
- Clipboard-Inhalt wird als Operand verwendet
- Result ersetzt Clipboard und wird gepastet
"""

from dataclasses import dataclass


@dataclass
class Command:
    trigger: str
    instruction: str


def detect(text: str, triggers: list[str]) -> Command | None:
    """Prüft ob `text` mit einem Trigger beginnt. Case-insensitive.

    Returns Command mit der Anweisung (Text ohne Trigger), oder None.
    """
    if not text or not triggers:
        return None

    stripped = text.strip()
    lower = stripped.lower()

    for trigger in triggers:
        trigger_lower = trigger.lower()
        if lower.startswith(trigger_lower):
            instruction = stripped[len(trigger):].strip()
            if not instruction:
                return None
            return Command(trigger=trigger, instruction=instruction)

    return None
