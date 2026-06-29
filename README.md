# Connect your Garmin to AI (free setup)

Pull your own Garmin data (workouts plus sleep, HRV, resting HR, body battery,
stress, training readiness) into a folder your AI coach reads, or into your own
database. This is the recovery data Strava cannot give you.

Built on the open-source **python-garminconnect** library by cyberjunky:
[github.com/cyberjunky/python-garminconnect](https://github.com/cyberjunky/python-garminconnect)

---

## Step 0: Get the files

Clone this repo or download the files. Open a terminal in the folder.

---

## Step 1: One-time setup

1. Install Python 3.11+ from python.org, then install the library:

   ```bash
   pip install -r requirements.txt
   ```

   On Windows, if `python`/`pip` is not found, use the `py` launcher:
   `py -m pip install -r requirements.txt`.

2. Log in once. This is the only time you enter your password or a 2FA code:

   ```bash
   export GARMIN_EMAIL="you@example.com"
   export GARMIN_PASSWORD="your-password"
   python sync_garmin.py --login
   ```

   Windows PowerShell:

   ```powershell
   $env:GARMIN_EMAIL="you@example.com"
   $env:GARMIN_PASSWORD="your-password"
   py sync_garmin.py --login
   ```

   It saves a login token on your computer that lasts about a year, then prints a
   long base64 token bundle. Copy that bundle somewhere safe if you plan to use
   Path A (GitHub Actions).

3. Test it:

   ```bash
   python sync_garmin.py --days 3 --dry-run
   ```

   You should see your last 3 days of activities and wellness print out.

---

## What you get

By default the script writes a clean folder your AI can read:

```text
garmin/
  daily/2026-06-28.md          # one wellness note per day, plain English
  activities/2026-06-28-...md  # one note per workout
  data.json                    # the full store, updated each run
```

A daily note looks like this:

```text
# Garmin wellness 2026-06-28
- Resting HR: 48 bpm
- HRV (overnight): 72 ms
- Sleep: 7.7 h (score 84)
- Body battery: 28 -> 96
- Stress (avg): 31
- Steps: 11240
- Training readiness: 81
```

---

## Path A: GitHub Actions (cloud, automatic)

1. Put the script in a GitHub repo. Copy `garmin-sync.yml` into `.github/workflows/`.

2. Add these secrets under Settings > Secrets and variables > Actions:

   | Secret | Value |
   |--------|-------|
   | `GARMIN_TOKEN_B64` | the base64 bundle printed by `--login` |
   | `GARMIN_INGEST_URL` | your ingest endpoint, if you use one |
   | `SESSION_LOG_SECRET` | the shared secret your endpoint checks |

3. Open the Actions tab and click **Run workflow** once to confirm a green run.

---

## Path B: Local cron (your computer, no GitHub)

**Mac / Linux:**

```bash
crontab -e
# run every morning at 6am:
0 6 * * * cd /path/to/garmin-ai && python sync_garmin.py --days 3 --sink files --out ./garmin
```

**Windows (Task Scheduler):** create a Basic Task that runs daily and calls:

```text
py C:\path\to\garmin-ai\sync_garmin.py --days 3 --sink files --out C:\path\to\garmin-ai\garmin
```

---

## Sending to a database instead of files

```bash
export GARMIN_INGEST_URL="https://yoursite.com/api/garmin/ingest"
export GARMIN_INGEST_SECRET="your-shared-secret"
python sync_garmin.py --days 3 --sink supabase
```

---

## Notes and limits

- This uses an unofficial login flow via [python-garminconnect](https://github.com/cyberjunky/python-garminconnect). If it stops working, update the library: `pip install -U garminconnect`, then re-run `--login`.
- Read-only. The script never writes anything back to your Garmin account.
- Keep your token bundle private. It is a login credential.
