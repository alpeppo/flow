"""System-Prompt-Builder für Groq-Cleanup.

v0.2.0: Drei Mode-Builder + Command-Builder.

- Verbatim: minimal-Cleanup, Stil bleibt
- Formal: gesprochen → geschrieben, Mail/Slack/WhatsApp
- Rage: Beleidigungen raus, diplomatisch
- Command: Trigger-Wort wendet Instruktion auf Clipboard-Text an
"""


def _hotwords_section(hotwords: list[str]) -> str:
    if not hotwords:
        return ""
    return f"\n\nBehalte folgende Eigennamen exakt bei: {', '.join(hotwords)}"


def build_verbatim_prompt(hotwords: list[str]) -> str:
    """Verbatim-Mode: minimal-Cleanup, Stil unverändert.

    Streng Wort-für-Wort: nichts hinzufügen, nichts umformulieren.
    """
    return f"""Du erhältst rohes Diktat aus Speech-to-Text.

WICHTIGSTE REGEL: Gib EXAKT die gesprochenen Wörter zurück, NICHTS ändern außer:
1. Füllwörter entfernen: äh, ähm, also, halt, ne, so, weißt du, eigentlich
2. Wort-Verdopplungen entfernen (z.B. "ich ich" → "ich")
3. Offensichtliche Versprecher entfernen
4. Zeichensetzung hinzufügen: Punkte, Kommas, Großschreibung am Satzanfang

VERBOTEN:
- KEINE Wörter hinzufügen die nicht gesagt wurden
- KEINE Begrüßungen einfügen ("Hey", "Hallo")
- KEINE Höflichkeitsfloskeln einfügen ("kannst du", "bitte")
- KEINE Umformulierungen ("Schreibe X" NICHT zu "Kannst du X schreiben")
- KEINE Satzumstellungen
- KEINE Stilanpassung

Beispiele:
Input: "äh schreibe kurz eine Mail"
Output: "Schreibe kurz eine Mail."

Input: "kann kann ich kurz mit dir sprechen"
Output: "Kann ich kurz mit dir sprechen?"

Antworte AUSSCHLIESSLICH mit dem minimal bereinigten Text.
Keine Anführungszeichen, keine Erklärung, kein Vor- oder Nachsatz.{_hotwords_section(hotwords)}"""


def build_formal_prompt(hotwords: list[str]) -> str:
    """Formal-Mode: gesprochene Sprache in geschriebene umformen.

    Wichtige Constraint: NICHT übertrieben formell.
    """
    return f"""Du erhältst rohes Diktat aus Speech-to-Text. Verwandle es in eine gut geschriebene Nachricht für E-Mail/Slack/WhatsApp:

- Entferne Füllwörter, Versprecher, Wort-Verdopplungen
- Forme gesprochene Sprache in geschriebene Sprache um:
  * Verkürzte Sätze ausformulieren ("Komm ich gleich" → "Ich komme gleich")
  * Umgangssprache → Schriftsprache ("Krass" → "beeindruckend", "Hey" → "Hallo")
  * Lange Schachtelsätze in klarere Sätze trennen
- WICHTIG: NICHT übertrieben formell werden. Es soll natürlich klingen, nur eben geschrieben statt gesprochen.
- Tonalität bleibt: locker bleibt locker, ernst bleibt ernst
- Keine erfundenen Inhalte hinzufügen
- Antworte AUSSCHLIESSLICH mit dem umgeformten Text
- Keine Anführungszeichen, keine Erklärung{_hotwords_section(hotwords)}"""


def build_rage_prompt(hotwords: list[str]) -> str:
    """Anti-Wut-Mode: emotionale Eskalation in diplomatische Sachlichkeit."""
    return f"""Du erhältst rohes Diktat aus Speech-to-Text. Der Sprecher ist gerade emotional/wütend. Deine Aufgabe: dasselbe Anliegen, aber diplomatisch.

- Entferne alle Beleidigungen, Schimpfwörter, persönliche Angriffe
- Übersetze emotionale Eskalation in sachliche Kritik:
  * "Dieser Idiot soll endlich kapieren" → "Ich würde mir wünschen, dass..."
  * "Das ist ein Scheißprodukt" → "Das Produkt erfüllt meine Erwartungen nicht weil..."
  * "Verdammte..." → einfach weglassen
- Behalte die KERN-Botschaft und das Anliegen vollständig bei
- Wenn ein Vorwurf da war, mache daraus eine konstruktive Bitte
- Tonalität: professionell-konstruktiv, nicht devot
- Keine erfundenen Inhalte
- Antworte AUSSCHLIESSLICH mit dem umgeformten Text
- Keine Anführungszeichen, keine Erklärung{_hotwords_section(hotwords)}"""


def build_command_prompt(instruction: str, target_text: str, hotwords: list[str]) -> str:
    """Prompt für Command-Mode: Instruktion auf Clipboard-Text anwenden."""
    return f"""Du führst eine Text-Transformation aus.

Anweisung des Users: {instruction}

Text auf den die Anweisung angewendet werden soll:
\"\"\"
{target_text}
\"\"\"

Antworte AUSSCHLIESSLICH mit dem transformierten Text.
Keine Anführungszeichen, keine Erklärung, kein Vor- oder Nachsatz.{_hotwords_section(hotwords)}"""
