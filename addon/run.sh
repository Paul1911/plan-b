#!/usr/bin/with-contenv bashio

# Read options from Home Assistant add-on config
SCHEDULE_TIME=$(bashio::config 'schedule_time')
SPOTIFY_ENABLED=$(bashio::config 'spotify_enabled')

# Store Tidal session and Spotify cache in /data (persistent across restarts)
export TIDAL_SESSION_FILE="/data/.tidal_session.json"

# Pass Spotify credentials as environment variables if enabled
if bashio::config.true 'spotify_enabled'; then
    export SPOTIFY_CLIENT_ID=$(bashio::config 'spotify_client_id')
    export SPOTIFY_CLIENT_SECRET=$(bashio::config 'spotify_client_secret')
    export SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"
    SPOTIFY_FLAG="--spotify"
else
    SPOTIFY_FLAG=""
fi

bashio::log.info "Starting 1Live Plan B scheduler at ${SCHEDULE_TIME} (Tue-Fri)"

cd /app
exec python3 -m plan_b schedule \
    --time "${SCHEDULE_TIME}" \
    --days tuesday wednesday thursday friday \
    ${SPOTIFY_FLAG}
