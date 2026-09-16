"""OpenSubtitles.com client: search for a movie and download its English subtitles.
This module only talks to the official OpenSubtitles REST API (no scraping).
"""
from __future__ import annotations
import re
import requests
import srt

API_BASE = "https://api.opensubtitles.com/api/v1"


class SubtitleError(Exception):
    """Raised when a subtitle search or download fails."""


def _headers(api_key: str) -> dict:
    return {
        "Api-Key": api_key,
        "User-Agent": "MovieShadowingApp v1.0",
        "Content-Type": "application/json",
    }


def search_movies(query: str, api_key: str) -> list[dict]:
    """Search for English subtitles matching a movie title.

    Returns a list of dicts: {title, year, release_name, file_id}.
    """
    try:
        resp = requests.get(
            f"{API_BASE}/subtitles",
            params={"query": query, "languages": "en", "type": "movie"},
            headers=_headers(api_key),
            timeout=15,
        )
    except requests.RequestException as e:
        raise SubtitleError(f"Could not reach OpenSubtitles: {e}") from e

    if resp.status_code == 401:
        raise SubtitleError("Invalid OpenSubtitles API key.")
    if resp.status_code != 200:
        raise SubtitleError(f"Search failed ({resp.status_code}): {resp.text[:200]}")

    results = []
    for item in resp.json().get("data", []):
        attrs = item.get("attributes", {})
        files = attrs.get("files", [])
        if not files:
            continue
        feature = attrs.get("feature_details", {}) or {}
        results.append(
            {
                "title": feature.get("title") or attrs.get("release") or query,
                "year": feature.get("year", "?"),
                "release_name": attrs.get("release", ""),
                "file_id": files[0]["file_id"],
            }
        )
    return results


def group_lines_into_chapters(lines: list[dict], min_gap_seconds: int = 30) -> list[dict]:
    """Groups a list of subtitle lines into chapters based on time gaps."""
    chapters = []
    current_chapter_lines = []
    current_chapter_start_time = None

    for i, line in enumerate(lines):
        if not current_chapter_lines:
            # Start a new chapter
            current_chapter_start_time = line['start']
            current_chapter_lines.append(line)
        else:
            # Check for a significant time gap between the current line and the last line of the current chapter
            prev_line_end = current_chapter_lines[-1]['end']
            if (line['start'] - prev_line_end) >= min_gap_seconds:
                # End current chapter and start a new one
                chapters.append({
                    'title': f"Chapter {len(chapters) + 1}", # Simple title for now
                    'start': current_chapter_start_time,
                    'end': current_chapter_lines[-1]['end'],
                    'lines': current_chapter_lines
                })
                current_chapter_lines = [line]
                current_chapter_start_time = line['start']
            else:
                current_chapter_lines.append(line)

    # Add the last chapter if any lines remain
    if current_chapter_lines:
        chapters.append({
            'title': f"Chapter {len(chapters) + 1}",
            'start': current_chapter_start_time,
            'end': current_chapter_lines[-1]['end'],
            'lines': current_chapter_lines
        })
    return chapters

def download_subtitle(file_id: int, api_key: str) -> list[dict]:
    """Download a subtitle file by its file_id and parse it into dialogue lines.

    Returns a list of dicts: {start, end, text} where start/end are seconds.
    """
    try:
        resp = requests.post(
            f"{API_BASE}/download",
            json={"file_id": file_id},
            headers=_headers(api_key),
            timeout=15,
        )
    except requests.RequestException as e:
        raise SubtitleError(f"Could not reach OpenSubtitles: {e}") from e

    if resp.status_code != 200:
        raise SubtitleError(f"Download request failed ({resp.status_code}): {resp.text[:200]}")

    payload = resp.json()
    link = payload.get("link")
    if not link:
        message = payload.get("message", "No download link returned.")
        raise SubtitleError(f"OpenSubtitles: {message}")

    try:
        file_resp = requests.get(link, timeout=15)
    except requests.RequestException as e:
        raise SubtitleError(f"Could not download subtitle file: {e}") from e

    if file_resp.status_code != 200:
        raise SubtitleError("Failed to fetch subtitle file content.")

    file_resp.encoding = file_resp.encoding or "utf-8"
    return parse_srt(file_resp.text)


def parse_srt(content: str) -> list[dict]:
    """Parse raw SRT text into a clean, deduplicated list of dialogue lines."""
    lines: list[dict] = []
    for sub in srt.parse(content):
        text = " ".join(sub.content.replace("\n", " ").split())
        text = re.sub(r"<[^>]+>", "", text).strip()  # strip <i>, <b>, etc.
        if not text:
            continue
        lines.append(
            {
                "start": sub.start.total_seconds(),
                "end": sub.end.total_seconds(),
                "text": text,
            }
        )
    return lines
