"""Text-to-speech abstraction.

`synthesize(text, accent)` is the only thing app.py depends on, so the
underlying engine can be swapped later (for a paid TTS API) without
touching the rest of the app.

Current implementation uses edge-tts, a free client for Microsoft Edge's
neural "read aloud" voices. No API key is needed, and voice quality is much
closer to natural speech than robotic TTS engines.
"""
import asyncio
import edge_tts

# Accent label -> Edge neural voice. 
ACCENT_VOICES = {
    "American English": "en-US-AriaNeural",
    "British English": "en-GB-SoniaNeural",
}


def synthesize(text: str, accent: str) -> bytes:
    """Generate MP3 speech audio for `text` spoken in the given `accent`."""
    voice = ACCENT_VOICES.get(accent, "en-US-AriaNeural")
    return asyncio.run(_synthesize_async(text, voice))


async def _synthesize_async(text: str, voice: str) -> bytes:
    audio = bytearray()
    communicate = edge_tts.Communicate(text, voice)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)
