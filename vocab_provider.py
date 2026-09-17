"""Vocabulary lookups for Movie Shadowing.

`explain_word(word, sentence)` is the only thing app.py depends on, keeping
this swappable (e.g. for a different LLM or a dictionary API) without
touching the rest of the app.

`select_vocab_words(sentence)` returns the words in a sentence worth
offering an explanation for. Stopwords, one-character words, and very
common English words (based on frequency in the NLTK Brown corpus) are
filtered out, so the UI only surfaces useful vocabulary for learners.
"""
import json
import os
import re

import nltk
from dotenv import load_dotenv
from groq import Groq

_MODEL = "openai/gpt-oss-20b"

# Lazy-loaded globals to prevent massive import times
_STOP_WORDS = None
_COMMON_WORDS = None


def _get_stop_words():
    global _STOP_WORDS
    if _STOP_WORDS is None:
        try:
            from nltk.corpus import stopwords
            _STOP_WORDS = set(stopwords.words("english"))
        except LookupError:
            nltk.download("stopwords", quiet=True)
            from nltk.corpus import stopwords
            _STOP_WORDS = set(stopwords.words("english"))
    return _STOP_WORDS


def _get_common_words():
    global _COMMON_WORDS
    if _COMMON_WORDS is None:
        try:
            from nltk.probability import FreqDist
            from nltk.corpus import brown
            try:
                _brown_words = [w.lower() for w in brown.words() if w.isalpha()]
            except LookupError:
                nltk.download("brown", quiet=True)
                _brown_words = [w.lower() for w in brown.words() if w.isalpha()]
            
            # The 1000 most frequent English words are too basic to be worth
            # explaining to a learner, so they're filtered out alongside stopwords.
            _COMMON_WORDS = {word for word, _ in FreqDist(_brown_words).most_common(1000)}
        except Exception:
            _COMMON_WORDS = {
                "know", "like", "see", "think", "go", "get",
                "make", "take", "say", "tell", "want",
            }
    return _COMMON_WORDS


class VocabError(Exception):
    """Raised when a vocabulary operation fails."""


def _get_client(api_key: str = None) -> Groq:
    if not api_key:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        
    if not api_key:
        raise VocabError("Please enter your Groq API key in the sidebar to enable word lookups.")
        
    return Groq(api_key=api_key)


def _sentence_words(sentence: str) -> list[str]:
    if not sentence:
        return []
    # Extract only valid alphabetic words or contractions
    return list(dict.fromkeys(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", sentence.lower())))


def select_vocab_words(sentence: str) -> list[str]:
    """Return the words in `sentence` worth explaining to a learner.

    Removes stopwords, one-character words, and very common words.
    """
    stopwords_set = _get_stop_words()
    common_words_set = _get_common_words()
    
    return [
        word for word in _sentence_words(sentence)
        if len(word) > 1 and word not in stopwords_set and word not in common_words_set
    ]


def filter_sentence_words(sentence: str) -> list[str]:
    """Alias kept for backwards compatibility."""
    return select_vocab_words(sentence)


def explain_word(word: str, sentence: str, api_key: str = None) -> str:
    """Explain `word`'s meaning as it's used in `sentence`."""
    if not word or not word.strip():
        raise VocabError("Vocabulary word cannot be empty.")
    if not sentence or not sentence.strip():
        raise VocabError("Sentence cannot be empty.")

    client = _get_client(api_key)

    prompt = f"""You are an English teacher helping a learner understand vocabulary.

Target word:
{word}

Sentence:
{sentence}

Explain ONLY the meaning of the target word as it is used in this sentence.

Return valid JSON only:

{{
  "easy_word": "one simple synonym or short equivalent phrase",
  "meaning_in_sentence": "a clear, simple explanation of the word's meaning in this exact context"
}}

Do not provide unrelated meanings.
Do not provide a dictionary-style list of meanings.
Do not add examples.
Do not add Markdown."""

    last_error = None
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                max_tokens=180,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from Groq.")

            content = content.strip()
            content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
            content = re.sub(r"\s*```$", "", content).strip()

            data = json.loads(content)
            easy_word = str(data.get("easy_word", "")).strip()
            meaning = str(data.get("meaning_in_sentence", "")).strip()

            if not easy_word or not meaning:
                raise ValueError("Groq response is missing required fields.")

            return f"**Simple meaning:** {easy_word}\n\n**In this context:** {meaning}"

        except Exception as e:
            last_error = e

    raise VocabError(f"Could not generate explanation for '{word}'.") from last_error
