# app.py
"""Movie Shadowing - practice English by listening to movie dialogue lines via TTS."""

import os
import streamlit as st

from pronunciation_provider import PronunciationError, analyze_pronunciation
from subtitle_provider import (
    SubtitleError,
    download_subtitle,
    search_movies,
    group_lines_into_chapters,
)
from tts_provider import ACCENT_VOICES, synthesize
from vocab_provider import VocabError, explain_word, select_vocab_words

st.set_page_config(page_title="Movie Shadowing", page_icon="🎬")

st.title("🎬 Movie Shadowing")
st.caption(
    "Find a movie's dialogue, then listen, look up words, and practice saying each line."
)

# --- Session state defaults ---
st.session_state.setdefault(
    "api_key",
    os.environ.get("OPENSUBTITLES_API_KEY", "")
)
st.session_state.setdefault("search_results", [])
st.session_state.setdefault("lines", None)
st.session_state.setdefault("lines_flat", [])
st.session_state.setdefault("chapters", [])
st.session_state.setdefault("movie_title", None)
st.session_state.setdefault("audio_cache", {})
st.session_state.setdefault("last_accent", None)
st.session_state.setdefault("active_line", None)
st.session_state.setdefault("vocab_target", None)
st.session_state.setdefault("pronunciation_results", {})
st.session_state.setdefault("recorder_nonce", 0)


# --- Sidebar: API key + accent ---
with st.sidebar:
    st.header("Settings")

    if not st.session_state.api_key:
        st.session_state.api_key = st.text_input(
            "OpenSubtitles API key",
            type="password",
            help="Free key from opensubtitles.com/consumers",
        )

    accent = st.radio("TTS accent", list(ACCENT_VOICES.keys()))

    st.caption("🇺🇸 American English · 🇬🇧 British English")
    st.caption("Word lookups need a GROQ_API_KEY environment variable.")


# Clear cached audio whenever the accent changes
if st.session_state.last_accent != accent:
    st.session_state.audio_cache = {}
    st.session_state.last_accent = accent

api_key = st.session_state.api_key

if not api_key:
    st.info("Enter your free OpenSubtitles API key in the sidebar to get started.")

@st.cache_data(show_spinner=False)
def _cached_explain_word(word: str, sentence: str) -> str:
    return explain_word(word, sentence)

# --- Movie search ---
movie_name = st.text_input(
    "Movie name",
    placeholder="e.g. Spider-Man: No Way Home"
)


if st.button("Find subtitles", disabled=not api_key) and movie_name:
    with st.spinner("Searching OpenSubtitles..."):
        try:
            st.session_state.search_results = search_movies(
                movie_name,
                api_key
            )
        except SubtitleError as e:
            st.session_state.search_results = []
            st.error(str(e))

    if not st.session_state.search_results:
        st.warning(
            "No English subtitles found for that title. Try a more exact name."
        )


# --- Pick a specific match and load its subtitles ---
if st.session_state.search_results:

    options = [
        f"{r['title']} ({r['year']}) — "
        f"{r['release_name'] or 'release n/a'}"
        for r in st.session_state.search_results
    ]

    choice = st.selectbox("Select a match", options)
    idx = options.index(choice)

    if st.button("Load dialogue"):
        with st.spinner("Downloading and parsing subtitles..."):
            try:
                selected = st.session_state.search_results[idx]

                # Download subtitles once
                lines = download_subtitle(
                    selected["file_id"],
                    api_key
                )

                # Keep the flat list
                st.session_state.lines_flat = lines

                # Group the same lines into chapters
                st.session_state.chapters = group_lines_into_chapters(lines)

                # Keep lines available for compatibility
                st.session_state.lines = lines

                st.session_state.movie_title = selected["title"]
                st.session_state.audio_cache = {}
                st.session_state.active_line = None
                st.session_state.vocab_target = None
                st.session_state.recorder_nonce = 0

            except SubtitleError as e:
                st.error(str(e))


# --- Dialogue list ---
if st.session_state.chapters:

    st.subheader(f"Dialogue — {st.session_state.movie_title}")

    total_lines = len(st.session_state.lines_flat)
    st.caption(f"{total_lines} lines · voice: {accent}")

    # Global index used for audio caching and active-line tracking
    global_line_idx = 0

    for chapter_idx, chapter in enumerate(st.session_state.chapters):
        # Expand the chapter containing the active line
        is_chapter_expanded = False

        if st.session_state.active_line is not None:
            chapter_start_global_idx = global_line_idx
            chapter_end_global_idx = (
                global_line_idx + len(chapter["lines"]) - 1
            )

            if (
                chapter_start_global_idx
                <= st.session_state.active_line
                <= chapter_end_global_idx
            ):
                is_chapter_expanded = True

        with st.expander(
            f"Chapter {chapter_idx + 1}: "
            f"{chapter['title']} "
            f"({len(chapter['lines'])} lines)",
            expanded=is_chapter_expanded,
        ):

            for line_in_chapter_idx, line in enumerate(chapter["lines"]):

                minutes, seconds = divmod(int(line["start"]), 60)
                timestamp = f"{minutes:02d}:{seconds:02d}"

                col_text, col_play, col_practice = st.columns([5, 1, 1])

                with col_text:
                    st.write(
                        f"**{timestamp}** — {line['text']}"
                    )

                with col_play:
                    if st.button(
                        "▶ Play",
                        key=f"play_chap{chapter_idx}_line{line_in_chapter_idx}",
                    ):
                        with st.spinner("Generating speech..."):
                            try:
                                st.session_state.audio_cache[
                                    global_line_idx
                                ] = synthesize(
                                    line["text"],
                                    accent
                                )
                            except Exception as e:
                                st.error(
                                    f"Could not generate audio: {e}"
                                )

                with col_practice:
                    if st.button(
                        "🔍 Practice",
                        key=f"practice_chap{chapter_idx}_line{line_in_chapter_idx}",
                    ):
                        st.session_state.active_line = global_line_idx
                        st.session_state.vocab_target = None
                        st.session_state.recorder_nonce = 0
                        st.rerun()

                # Play generated audio
                if global_line_idx in st.session_state.audio_cache:
                    st.audio(
                        st.session_state.audio_cache[global_line_idx],
                        format="audio/mp3",
                    )

                # --- Practice panel ---
                if st.session_state.active_line == global_line_idx:
                    with st.container(border=True):
                        st.markdown(
                            f"**Practicing:** {line['text']}"
                        )

                        # Filter out common and basic words for the UI
                        target_words = select_vocab_words(line["text"])
                        
                        if not target_words:
                            st.caption("No advanced vocabulary in this line.")
                        else:
                            st.caption("Click a word for a quick explanation:")
                            word_cols = st.columns(len(target_words))

                            for w_idx, (word, col) in enumerate(zip(target_words, word_cols)):
                                with col:
                                    if st.button(
                                        word,
                                        key=f"word_{global_line_idx}_{w_idx}",
                                    ):
                                        st.session_state.vocab_target = (
                                            word,
                                            line["text"],
                                        )

                        if st.session_state.vocab_target:
                            word, sentence = (
                                st.session_state.vocab_target
                            )

                            if word:
                                with st.spinner(
                                    f'Looking up "{word}"...'
                                ):
                                    try:
                                        st.info(
                                            _cached_explain_word(
                                                word,
                                                sentence,
                                            )
                                        )
                                    except VocabError as e:
                                        st.error(str(e))

                        st.divider()
                        st.caption(
                            "Record yourself saying this line:"
                        )

                        recording = st.audio_input(
                            "Record yourself",
                            key=(
                                f"recorder_{global_line_idx}_"
                                f"{st.session_state.recorder_nonce}"
                            ),
                            label_visibility="collapsed",
                        )

                        col_analyze, col_repeat = st.columns(2)

                        with col_analyze:
                            if st.button(
                                "Analyze",
                                disabled=recording is None,
                                key=f"analyze_{global_line_idx}",
                            ):
                                with st.spinner(
                                    "Analyzing pronunciation..."
                                ):
                                    try:
                                        result = analyze_pronunciation(
                                            recording.read(),
                                            line["text"],
                                        )

                                        st.metric(
                                            "Pronunciation score",
                                            f"{result['score']}/100",
                                        )

                                        st.write(
                                            result["feedback"]
                                        )

                                        if result["unclear_words"]:
                                            st.write(
                                                "**Words to review:** "
                                                + ", ".join(
                                                    result["unclear_words"]
                                                )
                                            )

                                        st.caption(
                                            f"We heard: "
                                            f"\u201c{result['transcript']}\u201d"
                                        )

                                    except PronunciationError as e:
                                        st.error(str(e))

                        with col_repeat:
                            if st.button(
                                "Repeat",
                                key=f"repeat_{global_line_idx}",
                            ):
                                st.session_state.recorder_nonce += 1
                                st.rerun()

                        if st.button(
                            "Close",
                            key=f"close_practice_{global_line_idx}",
                        ):
                            st.session_state.active_line = None
                            st.session_state.vocab_target = None
                            st.session_state.recorder_nonce = 0
                            st.rerun()

                global_line_idx += 1
