"""Tests für prompts.py — 3 Mode-Prompt-Builder."""

from wnflow.cleanup.prompts import (
    build_command_prompt,
    build_formal_prompt,
    build_rage_prompt,
    build_verbatim_prompt,
)


# --- Verbatim ---


def test_verbatim_prompt_mentions_filler_words() -> None:
    prompt = build_verbatim_prompt(hotwords=[])
    assert "Füllwörter" in prompt or "äh" in prompt.lower()


def test_verbatim_prompt_keeps_casual_tone_instruction() -> None:
    """Verbatim muss explizit sagen: Stil behalten."""
    prompt = build_verbatim_prompt(hotwords=[])
    assert "natürlichen Sprachstil" in prompt or "BEHALTE" in prompt


def test_verbatim_prompt_includes_hotwords() -> None:
    prompt = build_verbatim_prompt(hotwords=["Worknetic", "BZKI"])
    assert "Worknetic" in prompt
    assert "BZKI" in prompt


# --- Formal ---


def test_formal_prompt_mentions_email_target() -> None:
    prompt = build_formal_prompt(hotwords=[])
    assert "E-Mail" in prompt or "Slack" in prompt


def test_formal_prompt_demands_not_overly_formal() -> None:
    """Wichtige Constraint aus Spec: nicht übertrieben formell."""
    prompt = build_formal_prompt(hotwords=[])
    assert "NICHT übertrieben formell" in prompt or "natürlich klingen" in prompt


def test_formal_prompt_includes_hotwords() -> None:
    prompt = build_formal_prompt(hotwords=["Worknetic"])
    assert "Worknetic" in prompt


# --- Rage ---


def test_rage_prompt_mentions_insults_removal() -> None:
    prompt = build_rage_prompt(hotwords=[])
    assert "Beleidigungen" in prompt or "Schimpfwörter" in prompt


def test_rage_prompt_mentions_diplomatic() -> None:
    prompt = build_rage_prompt(hotwords=[])
    assert "diplomatisch" in prompt or "konstruktiv" in prompt


def test_rage_prompt_keeps_core_message() -> None:
    """Spec: KERN-Botschaft beibehalten."""
    prompt = build_rage_prompt(hotwords=[])
    assert "KERN-Botschaft" in prompt or "Anliegen vollständig" in prompt


def test_rage_prompt_includes_hotwords() -> None:
    prompt = build_rage_prompt(hotwords=["Worknetic"])
    assert "Worknetic" in prompt


# --- Cross-Mode ---


def test_all_modes_demand_no_quotes() -> None:
    """Alle Modi sollen klarstellen: keine Anführungszeichen im Output."""
    for builder in (build_verbatim_prompt, build_formal_prompt, build_rage_prompt):
        prompt = builder(hotwords=[])
        assert (
            "Anführungszeichen" in prompt
            or "AUSSCHLIESSLICH" in prompt
            or "ohne Erklärung" in prompt.lower()
        ), f"Builder {builder.__name__} fehlt no-quotes-Instruction"


def test_all_modes_work_without_hotwords() -> None:
    for builder in (build_verbatim_prompt, build_formal_prompt, build_rage_prompt):
        prompt = builder(hotwords=[])
        assert len(prompt) > 100, f"{builder.__name__} prompt zu kurz"


# --- Command-Prompt unverändert (aus v0.1.0) ---


def test_command_prompt_includes_instruction_and_text() -> None:
    prompt = build_command_prompt(
        instruction="mach das kürzer",
        target_text="Sehr geehrter Herr Müller, ich schreibe Ihnen heute...",
        hotwords=[],
    )
    assert "mach das kürzer" in prompt
    assert "Sehr geehrter Herr Müller" in prompt
