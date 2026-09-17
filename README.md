# Movie-Shadowing-App
Web App for Practice English by listening to and repeating movie dialogue lines, spoken by a text-to-speech voice in the accent of your choice.


## How it works
 
1. You type a movie name.
2. The app searches [OpenSubtitles.com](https://www.opensubtitles.com) for an
   English subtitle file and downloads it (official API only — no scraping).
3. The subtitle lines are parsed and shown as a clickable list with timestamps.
4. Clicking ▶ Play on a line generates that line's audio with TTS and plays it.
5. A sidebar toggle switches the voice between American and British English.
6. Clicking 🔍 Practice on a line opens a panel where you can:
   - Click any word in that line for a short, learner-friendly explanation
     (simple meaning + what it means in that specific sentence).
   - Record yourself saying the line and get a pronunciation score, overall
     feedback, and a list of words that came through unclear.
Movie audio/video is never used or required — only text dialogue + TTS.
 
## Setup
 
1. Install dependencies:
```bash
   pip install -r requirements.txt
```
 
2. Get a free OpenSubtitles API key: create a "consumer" at
   https://www.opensubtitles.com/en/consumers (just needs a free account).
3. Provide the key either as an environment variable...
```bash
   export OPENSUBTITLES_API_KEY=your_key_here
```
 
   ...or paste it into the sidebar field when the app is running.
 
4. (Optional) For word lookups, set a Groq API key:
```bash
   export GROQ_API_KEY=your_key_here
```
 
   Get a free one at https://console.groq.com. Without it, everything else
   still works — clicking a word will just show an error asking for the key.
 
5. Run the app:
```bash
   streamlit run app.py
```
