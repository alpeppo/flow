"""System-Prompt-Builder für Groq-Cleanup.

Zwei Modi:
- Diktat: rohes STT wird bereinigt (Füllwörter weg, Grammatik fix, Stil bleibt)
- Command: User-Instruktion wird auf Clipboard-Text angewendet
"""


def build_dictation_prompt(hotwords: list[str]) -> str:
    """Prompt für Standard-Diktat-Bereinigung."""
    hotwords_section = ""
    if hotwords:
        hotwords_section = (
            f"\n\nBehalte folgende Eigennamen exakt bei: {', '.join(hotwords)}"
        )

    return f"""Du erhältst rohes Diktat aus Speech-to-Text. Bereinige es:
- Entferne Füllwörter (äh, ähm, also, halt, ne, so)
- Korrigiere offensichtliche Grammatik- und Satzbaufehler
- Behalte Bedeutung, Stil und Tonalität exakt bei
- Korrigiere Zeichensetzung (Punkte, Kommas, Großschreibung)
- Antworte AUSSCHLIESSLICH mit dem bereinigten Text
- Keine Anführungszeichen, keine Erklärung, kein Vor- oder Nachsatz{hotwords_section}"""


def build_command_prompt(instruction: str, target_text: str, hotwords: list[str]) -> str:
    """Prompt für Command-Mode: Instruktion auf Clipboard-Text anwenden."""
    hotwords_section = ""
    if hotwords:
        hotwords_section = (
            f"\nBehalte folgende Eigennamen exakt bei: {', '.join(hotwords)}\n"
        )

    return f"""Du führst eine Text-Transformation aus.

Anweisung des Users: {instruction}

Text auf den die Anweisung angewendet werden soll:
\"\"\"
{target_text}
\"\"\"

Antworte AUSSCHLIESSLICH mit dem transformierten Text.
Keine Anführungszeichen, keine Erklärung, kein Vor- oder Nachsatz.{hotwords_section}"""
