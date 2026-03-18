#!/bin/sh

# Read options from Home Assistant add-on config (/data/options.json)
CONFIG="/data/options.json"
SCHEDULE_TIME=$(python3 -c "import json; print(json.load(open('${CONFIG}'))['schedule_time'])")

# Store Tidal session in /data (persistent across restarts)
export TIDAL_SESSION_FILE="/data/.tidal_session.json"

# Check Spotify config
SPOTIFY_ENABLED=$(python3 -c "import json; print(json.load(open('${CONFIG}'))['spotify_enabled'])")
SPOTIFY_FLAG=""
if [ "$SPOTIFY_ENABLED" = "True" ]; then
    export SPOTIFY_CLIENT_ID=$(python3 -c "import json; print(json.load(open('${CONFIG}'))['spotify_client_id'])")
    export SPOTIFY_CLIENT_SECRET=$(python3 -c "import json; print(json.load(open('${CONFIG}'))['spotify_client_secret'])")
    export SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"
    SPOTIFY_FLAG="--spotify"
fi

echo "Starting 1Live Plan B scheduler at ${SCHEDULE_TIME} (Tue-Fri)"

cd /app
exec python3 -m plan_b schedule \
    --time "${SCHEDULE_TIME}" \
    --days tuesday wednesday thursday friday \
    ${SPOTIFY_FLAG}
