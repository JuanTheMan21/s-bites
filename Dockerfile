# One image, two roles -- api and worker. Which one runs is picked by the `command` each
# Container App sets (see infra/main.bicep), not by anything baked in here. Neither role needs
# web/ (a separate Static Web Apps deploy, T38) or tests/ (offline-only, never shipped).
#
# python:3.11-slim matches pyproject.toml's `requires-python = ">=3.11"` exactly, and is Debian-
# based so ffmpeg/Node/Playwright's system libraries all install cleanly via apt.
FROM python:3.11-slim

WORKDIR /app

# ffmpeg: mux/ shells out to it directly, never moviepy (CLAUDE.md). curl/ca-certificates: needed
# to fetch the NodeSource setup script and for Node's own npm registry access during `npm install`.
# gnupg: NodeSource's setup script needs it to verify the repo signing key. unzip: found live, not
# assumed -- @puppeteer/browsers (below) extracts chrome-headless-shell's downloaded archive with
# it and has no fallback; python:3.11-slim doesn't ship it, and the very first real build failed
# on exactly this with no ambiguity in the error.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        gnupg \
        unzip \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- Node side: the pinned HyperFrames CLI (adapters/local/hyperframes_process.py) -------------
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
# HyperFrames' Chrome Headless Shell is fetched via puppeteer-core + @puppeteer/browsers, which
# does NOT happen automatically on `npm install` (puppeteer-core alone never downloads a browser --
# confirmed while planning this image). Without this, the first render in a fresh container would
# block on a runtime network fetch -- exactly the "locked-down container" problem this project
# already solved for GSAP by vendoring it (rendering/templates/vendor/gsap.min.js).
RUN npx @puppeteer/browsers install chrome-headless-shell

# --- Python side ---------------------------------------------------------------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# --with-deps pulls the Debian system libraries Chromium needs (fonts, X11 libs) that apt alone
# would otherwise miss piecemeal -- Playwright's own recommended install path for a bare image.
RUN playwright install --with-deps chromium

# --- Application code -----------------------------------------------------------------------
# Not web/ (T38's own Static Web Apps deploy), not tests/, not .claude/ -- see .dockerignore for
# the full exclusion list this COPY is filtered through.
COPY . .

# No CMD/ENTRYPOINT here on purpose -- each Container App (infra/main.bicep) sets its own
# `command`: uvicorn for the api app, `python worker.py` for the worker app. Never add --reload
# to whichever uvicorn command is set at the Container App level -- api/main.py's own docstring
# explains why, and while that specific Windows failure mode doesn't apply on Linux, --reload
# is still unnecessary and wrong for a deployed container regardless.
