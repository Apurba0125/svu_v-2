#!/usr/bin/env bash
# Render build step. Any failure must abort the deploy.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Hashed + compressed static assets served by WhiteNoise.
python manage.py collectstatic --no-input

python manage.py migrate --no-input

# First deploy: populate demo content. Later deploys: skip seeding but restore
# any generated imagery lost to Render's ephemeral filesystem.
python manage.py seed_data --only-if-empty
