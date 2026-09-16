"""Pronunciation feedback for Movie Shadowing.

Current implementation transcribes the learner's recording with free,
keyless speech recognition, then compares the transcript to the target line
to produce a score, overall feedback, and a list of unclear words. This is a
practical proxy for pronunciation quality: words the recognizer couldn't
match are usually the ones spoken unclearly.
"""
import difflib
import io
import re
import speech_recognition as sr


class PronunciationError(Exception):
    """Raised when a recording can't be analyzed."""


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def analyze_pronunciation(audio_bytes: bytes, target_text: str) -> dict:
    """Transcribe `audio_bytes` and compare it against `target_text`.

    Returns {"score": int, "transcript": str, "feedback": str, "unclear_words": list[str]}.
    """
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
        transcript = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return {
            "score": 0,
            "transcript": "",
            "feedback": "Couldn't make out any speech. Try again, a bit closer to the microphone.",
            "unclear_words": [],
        }
    except sr.RequestError as e:
        raise PronunciationError(f"Speech recognition service unavailable: {e}") from e

    target_words = _words(target_text)
    said_words = _words(transcript)

    matcher = difflib.SequenceMatcher(None, target_words, said_words)
    score = round(matcher.ratio() * 100)

    matched_idxs = set()
    for block in matcher.get_matching_blocks():
        matched_idxs.update(range(block.a, block.a + block.size))
    unclear_words = [w for i, w in enumerate(target_words) if i not in matched_idxs]

    if score >= 90:
        feedback = "Excellent! That was very close to the target line."
    elif score >= 70:
        feedback = "Good effort — most words were clear, a few need more practice."
    elif score >= 40:
        feedback = "Some words came through, but several were unclear. Try speaking a bit slower."
    else:
        feedback = "Hard to match to the target line. Try again, speaking clearly at a natural pace."

    return {
        "score": score,
        "transcript": transcript,
        "feedback": feedback,
        "unclear_words": unclear_words,
    }
