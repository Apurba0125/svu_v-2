# Swami Vivekananda University — Website

A Django 4.2 implementation of the SVU website: fully responsive, content-managed
through the Django admin, and hardened against the usual web attack surface.

Built with **no external CDN, font, or JavaScript dependency** — every asset is
self-hosted, which is what allows the Content-Security-Policy to stay locked to
`'self'` with no `unsafe-inline`.

---

## 1. Quick start

```bash
pip install -r requirements.txt

cp .env.example .env                       # then edit it
python manage.py generate_secret_key       # paste the output into .env

python manage.py migrate
python manage.py seed_data                 # demo content + generated imagery
python manage.py createsuperuser
python manage.py runserver
```

| URL | What |
|---|---|
| http://127.0.0.1:8000/ | the site |
| http://127.0.0.1:8000/manage-svu-a91f/ | admin (path is set by `DJANGO_ADMIN_URL`) |

`seed_data` is idempotent — re-run it any time. `--flush-content` rebuilds the
demo content from scratch (it never touches users or captured enquiries).

---

## 2. Project layout

```
svu_site/settings/   base.py · dev.py · prod.py   (prod refuses to boot if misconfigured)
core/                site chrome, home page, flat pages, search, contact,
                     security middleware, CAPTCHA, validators
academics/           schools, departments, programme levels, courses, facilities, partners
admissions/          states/cities, enquiry capture, scholarships, admission steps
events/              notice board, events + photo galleries
templates/           base.html + includes/ + one folder per app + errors/
static/css/main.css  the whole design system (mobile-first)
static/js/main.js    carousels, drawer nav, AJAX enquiry — vanilla, no deps
```

---

## 3. Page sections → where to edit them

Everything on the home page is admin-managed; nothing is hard-coded in a template.

| Home page section | Admin model |
|---|---|
| Top bar links / social icons | Menu items *(Top utility bar)* / Social links |
| Header phones, address, CTAs, marquee | **Site configuration** (single row) |
| Main navigation + dropdowns | Menu items *(Main navigation)* — set a Parent for children |
| Hero carousel | Hero slides |
| Notice Board | Notices |
| Welcome text + arrow shortcuts | Site configuration · Quick links |
| Enquiry form | Programme levels, Courses, States, Cities |
| We are now enlisted | Enlistments |
| Explore our offerings | Offerings |
| SVU Schools carousel | Schools |
| Video features | Video features (store the YouTube **ID** only) |
| Latest Events carousel | Events |
| Chancellor's message | Chancellor's message |
| Centres timeline | Centres |
| THE SVUites | Testimonials |
| Footer link columns | Footer links |

---

## 4. Responsive behaviour

Mobile-first CSS with breakpoints at **400 / 576 / 768 / 992 / 1200 / 1440 px**,
plus dedicated handling for landscape phones, very small phones (≤380 px), print,
and `prefers-reduced-motion`.

- **< 992 px** — the navigation becomes a slide-in drawer with tap-to-expand
  accordions, a scrim, ESC-to-close and body scroll-lock.
- **Carousels** use CSS scroll-snap, so they are natively swipeable and work
  even with JavaScript disabled. Cards per view: 1 → 2 → 3 → 4 as width grows.
- **Touch targets** are ≥ 44 px on every control; form inputs are 44 px minimum.
- **Images** carry explicit `width`/`height` and `loading="lazy"` (the first
  hero slide is `eager`/`fetchpriority=high`) so there is no layout shift.
- **Tables and wide content** scroll inside their own container — the page body
  never scrolls horizontally.

Accessibility: skip link, visible focus rings, ARIA labelling on all icon-only
controls, `sr-only` labels on every form field, and semantic landmarks.

---

## 5. Security

Run `python manage.py check --deploy --settings=svu_site.settings.prod` — it
currently reports **0 issues**.

### Transport & headers
- HSTS (1 year, preload, includeSubDomains), SSL redirect, secure cookies
- **CSP with a per-request nonce** — no `unsafe-inline`, no `unsafe-eval`,
  `object-src 'none'`, `frame-ancestors 'none'`, `base-uri`/`form-action` locked
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy`, `Permissions-Policy` (all sensors/camera/mic denied),
  COOP + CORP, `X-Permitted-Cross-Domain-Policies: none`
- `SECURE_PROXY_SSL_HEADER` is only trusted when `DJANGO_BEHIND_PROXY=True`,
  so a client can never spoof HTTPS on a direct-facing deployment

### Injection & XSS
- ORM-only queries (no raw SQL, no string interpolation anywhere)
- Django autoescaping everywhere; admin rich text is **sanitised with bleach on
  save *and* again on render**, so a row written directly to the DB still cannot
  inject script
- Control/zero-width character stripping and injection heuristics on public input
- CSV export escapes `= + - @` to defuse spreadsheet formula injection

### Forms & abuse
Public forms carry four independent layers on top of CSRF:
1. **Honeypot** field, hidden from humans
2. **Signed timestamp** — rejects sub-3-second (scripted) submissions and tampering
3. **Image CAPTCHA** — answer stored only as a salted HMAC in the session,
   single-use (never replayable) and time-limited
4. **Cache-backed rate limiting** per IP, returning `429` + `Retry-After`

Quotas are deliberately generous enough that a visitor fumbling the CAPTCHA five
times is still not locked out (there is a regression test for exactly that).

### Uploads
Three-axis validation: extension allow-list, **real decoded content** (Pillow
`verify()` / magic bytes), and size. SVGs are scanned for scripts, event
handlers, external references and entities. Client filenames are discarded
entirely and replaced with a slug + random suffix, which kills path traversal,
media overwrites and double-extension tricks.

### Authentication & admin
- Admin mounted at an unguessable path; **prod refuses to start if it is `admin/`**
- Failed-login lockout per IP + full authentication audit log
- 12-character minimum passwords, `no-store` on all authenticated responses
- Every admin write and error logged to `logs/security.log`

### Privacy
Enquiries are read-only in the admin, mobile numbers are masked in list views,
export is superuser-only, and consent wording + provenance are recorded per
submission. `python manage.py purge_old_enquiries --days 730` enforces retention
(`--dry-run` to preview) — schedule it monthly.

### Third parties
YouTube embeds use a **click-to-load facade**: nothing is requested from Google
until the visitor presses play, and the embed then uses `youtube-nocookie.com`.
The Facebook footer widget was deliberately replaced with a plain link rather
than loading their SDK, which would have required weakening the CSP.

---

## 6. Deploying to Render

The repo ships a Blueprint (`render.yaml`) that provisions the web service and a
Postgres database together and wires `DATABASE_URL` automatically.

1. **Render ▸ New ▸ Blueprint** and connect `Apurba0125/svu_v-2`.
2. Render reads `render.yaml` and prompts for the one secret it will not invent:

   ```bash
   python manage.py generate_secret_key    # paste the output as DJANGO_SECRET_KEY
   ```

   (It is not auto-generated because Render's `generateValue` is 44 characters,
   which trips Django's own `security.W009` 50-character rule.)
3. **Change `DJANGO_ADMIN_URL`** in `render.yaml` from the committed default to
   your own unguessable path before the first deploy.
4. Apply. `build.sh` installs dependencies, runs `collectstatic`, applies
   migrations, and seeds demo content on the first deploy only
   (`seed_data --only-if-empty`).
5. Create your login once the service is live:
   **Render ▸ svu-website ▸ Shell** → `python manage.py createsuperuser`

`ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` pick up `RENDER_EXTERNAL_HOSTNAME`
automatically, so the `.onrender.com` URL works before you attach a domain. Add
your real domain to `DJANGO_ALLOWED_HOSTS` when you do.

### Free-tier caveats

| Limit | Effect | Fix |
|---|---|---|
| Ephemeral filesystem | Uploaded media is **lost on every deploy** | Attach a Render Disk, or move media to S3/Cloudinary |
| Free Postgres is time-limited | Database is deleted when it expires — check the current window on Render's pricing page | Upgrade the database plan |
| Service sleeps after 15 min idle | ~30 s cold start | Upgrade the service plan |
| `LocMemCache` is per-process | Rate limits apply per worker, not globally | Add Redis and set `REDIS_URL` |

Because the disk is ephemeral, `seed_data` re-checks storage on every deploy and
regenerates any missing generated imagery — so the demo site never comes back
with broken images. That safety net does **not** cover files an editor uploaded
through the admin: for those you need a Disk or object storage.

`DJANGO_SERVE_MEDIA=True` makes the app serve `/media/` through WhiteNoise, since
a single Render service has no nginx in front. It is fine for public read-only
imagery; switch to object storage before relying on user uploads at scale.

---

## 7. Production deployment (any other host)

```bash
export DJANGO_SETTINGS_MODULE=svu_site.settings.prod
export DJANGO_SECRET_KEY="<60+ random chars>"
export DJANGO_ALLOWED_HOSTS="www.svu.ac.in,svu.ac.in"
export DJANGO_CSRF_TRUSTED_ORIGINS="https://www.svu.ac.in"
export DJANGO_ADMIN_URL="<something-unguessable>/"
export DJANGO_BEHIND_PROXY=True          # only if a reverse proxy terminates TLS

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn svu_site.wsgi:application       # or waitress-serve on Windows
```

`prod.py` raises `ImproperlyConfigured` rather than booting insecurely when the
secret key is weak/missing, `ALLOWED_HOSTS` is still the localhost default, or
the admin is left on `admin/`.

**Two things the app cannot do for you:**

1. **Serve `/media/`.** WhiteNoise handles `/static/` only. Add an nginx rule
   (or equivalent) for `/media/`, and serve it **without** executing anything:

   ```nginx
   location /media/ {
       alias /srv/svu/media/;
       add_header X-Content-Type-Options nosniff;
       add_header Content-Disposition "attachment" always;   # for documents
   }
   ```
2. **Set up Redis.** The default `LocMemCache` is per-process, so rate limits and
   login lockouts are only enforced per worker. Set `REDIS_URL` in production to
   make them global.

---

## 8. Tests

```bash
python manage.py test              # 50 tests
```

Covering: security headers and CSP nonce rotation, probe/traversal blocking,
admin exposure, HTML sanitisation and stored-XSS, rate limiting, upload
validators, and the full enquiry pipeline (honeypot, timing, CAPTCHA replay,
consent, cross-field integrity, CSRF, throttling).

---

## 9. Branding

The header shows the university crest from `static/img/logo.jpeg` beside a text
lockup, because the wordmark inside the circular crest is unreadable at header
size on its own. Uploading a **Logo** in admin › Site configuration overrides the
bundled static crest without any code change.

The crest's dark teal is exposed as the `--brand` CSS token
(`#14463f`, in `static/css/main.css`) and is used for the wordmark; the gold
palette from the original design drives the rest of the chrome.
`static/img/favicon.svg` mirrors the crest.

---

## 10. ⚠ Placeholder content you MUST replace before launch

This site was built from screenshots of a *different* university. Anything that
was a real-world fact about that institution has been deliberately replaced with
an obvious placeholder rather than carried over or guessed — so **nothing here
misdirects a real applicant**, but several fields are intentionally not real:

| Where | Current value | Action |
|---|---|---|
| Site configuration › phones | `+91 90000 00001/2` | set the real helpline |
| Site configuration › toll free | `1800 000 0000` | set the real number |
| Site configuration › address | "University Campus, Kolkata, West Bengal" | set the real campus address |
| Site configuration › email / website | `info@svu.ac.in` / `www.svu.ac.in` | confirm the real domain |
| Site configuration › WhatsApp | `919000000001` | set the real number |
| Welcome text & *About SVU* page | no Act/year cited | add the University's own establishment details |
| Chancellor's message | name is "The Chancellor" | set the real name and photo |
| Scholarships / Quick links | "University Scholarship Foundation" | rename to the real foundation |
| Video features | two placeholder YouTube IDs | swap for real videos |
| Social links & Pay Fee URL | generic / `#` | point at the real accounts |

Other notes:

- **Imagery is generated, not real.** `seed_data` synthesises stand-in slides,
  school cards, event photos, logos and portraits with Pillow. Replace them
  through the admin — every model has an upload field ready.
- **Schools, courses, events and notices are illustrative** demo content
  modelled on a typical university structure. Edit or delete freely.
- **Third-party links** (UGC, Shodhganga, Ministry of Education) point at the
  real public URLs; university-specific ones are placeholders.
