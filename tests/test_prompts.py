"""Tests für prompts.py — System-Prompt-Builder mit Hotwords."""

from wnflow.cleanup.prompts import build_command_prompt, build_dictation_prompt


def test_dictation_prompt_contains_filler_word_instruction() -> None:
    prompt = build_dictation_prompt(hotwords=[])
    assert "Füllwörter" in prompt or "äh" in prompt.lower()


def test_dictation_prompt_contains_hotwords() -> None:
    prompt = build_dictation_prompt(hotwords=["Worknetic", "Ridersystem"])
    assert "Worknetic" in prompt
    assert "Ridersystem" in prompt


def test_dictation_prompt_without_hotwords_works() -> None:
    prompt = build_dictation_prompt(hotwords=[])
    assert len(prompt) > 50  # nicht-trivialer Prompt


def test_command_prompt_includes_instruction_and_text() -> None:
    prompt = build_command_prompt(
        instruction="mach das kürzer",
        target_text="Sehr geehrter Herr Müller, ich schreibe Ihnen heute...",
        hotwords=[],
    )
    assert "mach das kürzer" in prompt
    assert "Sehr geehrter Herr Müller" in prompt


def test_command_prompt_with_hotwords() -> None:
    prompt = build_command_prompt(
        instruction="übersetze ins Englische",
        target_text="Hallo Worknetic Team",
        hotwords=["Worknetic"],
    )
    assert "Worknetic" in prompt


def test_dictation_prompt_demands_clean_output() -> None:
    """Prompt muss klar machen dass Output keine Anführungszeichen/Erklärung enthält."""
    prompt = build_dictation_prompt(hotwords=[])
    assert "Anführungszeichen" in prompt or "ohne Erklärung" in prompt.lower() or "ausschließlich" in prompt.lower()
