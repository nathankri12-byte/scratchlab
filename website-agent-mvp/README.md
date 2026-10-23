# Website Agent MVP

An isolated MVP for discovering potential business website prospects, checking their public websites, scoring them, and generating review-only demo concepts. It does not send emails automatically.

## Safety and cost controls
- Dashboard requires `DASHBOARD_PASSWORD` and `SECRET_KEY` environment variables.
- Gemini is optional. Without `GEMINI_API_KEY`, the app runs deterministic checks only and labels AI analysis as unavailable.
- `MAX_CANDIDATES_PER_RUN` limits work per run.
- Company discovery uses public OpenStreetMap/Overpass data and may be incomplete. It must respect service policies and rate limits; this is a prototype, not a comprehensive German business registry.
- No email sending, no automatic public demo deployment, no credential collection from target websites.
- Demos are drafts and must be checked for accuracy, copyright, contact details, and consent before sharing.

## Local run
```bash
cd website-agent-mvp
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
export DASHBOARD_PASSWORD='choose-a-strong-password'
export SECRET_KEY='a-long-random-secret'
export GEMINI_API_KEY='your-key-if-you-have-one'
python app.py
```
Then open http://127.0.0.1:5000.

## Render
Create a web service from the existing repository `nathankri12-byte/scratchlab`, branch `main`, using the root `render.yaml` blueprint. The service is configured to use this folder only; it does not modify ScratchLab's app files. Set `DASHBOARD_PASSWORD` in Render's environment settings before opening the dashboard. Set `GEMINI_API_KEY` only in Render Environment, never in GitHub or chat.

## MVP workflow
1. Trigger one discovery run from the dashboard.
2. Review candidate company names, source URLs, and website status.
3. Run the technical/heuristic evaluation.
4. Generate an HTML draft for a selected candidate.
5. Review the draft and test it locally before sharing.

The discovery step queries a small, rotating list of German city centers and common business tags. It is intentionally capped to keep the MVP gentle on public services and free hosting. Expand only after testing reliability and legal requirements.
