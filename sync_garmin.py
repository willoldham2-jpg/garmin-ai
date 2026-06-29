import argparse
import base64
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import garminconnect
except ImportError:
    sys.exit("Run: pip install -r requirements.txt")


TOKEN_PATH = Path.home() / ".garminconnect"


def get_client():
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    token_b64 = os.environ.get("GARMIN_TOKEN_B64", "")

    client = garminconnect.Garmin(email, password)

    if token_b64:
        token_data = json.loads(base64.b64decode(token_b64))
        client.garth.loads(token_data)
    elif TOKEN_PATH.exists():
        client.garth.loads(json.loads(TOKEN_PATH.read_text()))
    else:
        sys.exit("Not logged in. Run with --login first.")

    return client


def do_login():
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    if not email or not password:
        sys.exit("Set GARMIN_EMAIL and GARMIN_PASSWORD before running --login.")

    client = garminconnect.Garmin(email, password)
    client.login()

    token_data = client.garth.dumps()
    TOKEN_PATH.write_text(json.dumps(token_data))

    b64 = base64.b64encode(json.dumps(token_data).encode()).decode()
    print("Login successful. Token saved to", TOKEN_PATH)
    print("\nGARMIN_TOKEN_B64 (copy this into your GitHub secret):\n")
    print(b64)


def fetch_wellness(client, day: date) -> dict:
    ds = day.isoformat()
    data = {}

    try:
        stats = client.get_stats(ds)
        data["resting_hr"] = stats.get("restingHeartRate")
        data["steps"] = stats.get("totalSteps")
        data["stress_avg"] = stats.get("averageStressLevel")
        data["body_battery_high"] = stats.get("bodyBatteryHighestValue")
        data["body_battery_low"] = stats.get("bodyBatteryLowestValue")
    except Exception:
        pass

    try:
        sleep = client.get_sleep_data(ds)
        daily = sleep.get("dailySleepDTO", {})
        data["sleep_seconds"] = daily.get("sleepTimeSeconds")
        data["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
    except Exception:
        pass

    try:
        hrv = client.get_hrv_data(ds)
        summary = hrv.get("hrvSummary", {})
        data["hrv"] = summary.get("lastNight")
    except Exception:
        pass

    try:
        readiness = client.get_training_readiness(ds)
        if isinstance(readiness, list) and readiness:
            data["training_readiness"] = readiness[0].get("score")
        elif isinstance(readiness, dict):
            data["training_readiness"] = readiness.get("score")
    except Exception:
        pass

    return data


def wellness_to_md(day: date, w: dict) -> str:
    lines = [f"# Garmin wellness {day.isoformat()}"]

    if w.get("resting_hr"):
        lines.append(f"- Resting HR: {w['resting_hr']} bpm")
    if w.get("hrv"):
        lines.append(f"- HRV (overnight): {w['hrv']} ms")
    if w.get("sleep_seconds"):
        hours = round(w["sleep_seconds"] / 3600, 1)
        score = w.get("sleep_score", "?")
        lines.append(f"- Sleep: {hours} h (score {score})")
    if w.get("body_battery_low") is not None and w.get("body_battery_high") is not None:
        lines.append(f"- Body battery: {w['body_battery_low']} -> {w['body_battery_high']}")
    if w.get("stress_avg"):
        lines.append(f"- Stress (avg): {w['stress_avg']}")
    if w.get("steps"):
        lines.append(f"- Steps: {w['steps']}")
    if w.get("training_readiness"):
        lines.append(f"- Training readiness: {w['training_readiness']}")

    return "\n".join(lines) + "\n"


def fetch_activities(client, day: date) -> list:
    ds = day.isoformat()
    try:
        acts = client.get_activities_by_date(ds, ds)
        return acts or []
    except Exception:
        return []


def activity_to_md(act: dict) -> str:
    name = act.get("activityName", "Activity")
    atype = act.get("activityType", {}).get("typeKey", "unknown")
    start = (act.get("startTimeLocal") or "")[:10]
    duration_s = act.get("duration", 0)
    duration_min = round(duration_s / 60)
    distance_m = act.get("distance", 0)
    distance_km = round(distance_m / 1000, 2) if distance_m else None
    avg_hr = act.get("averageHR")
    calories = act.get("calories")

    lines = [f"# {name} — {start}"]
    lines.append(f"- Type: {atype}")
    lines.append(f"- Duration: {duration_min} min")
    if distance_km:
        lines.append(f"- Distance: {distance_km} km")
    if avg_hr:
        lines.append(f"- Avg HR: {avg_hr} bpm")
    if calories:
        lines.append(f"- Calories: {calories}")

    return "\n".join(lines) + "\n"


def sync(days: int, sink: str, out: Path, dry_run: bool):
    client = get_client()
    today = date.today()

    all_wellness = {}
    all_activities = []

    for i in range(days):
        day = today - timedelta(days=i)
        print(f"Fetching {day.isoformat()}...")

        wellness = fetch_wellness(client, day)
        activities = fetch_activities(client, day)

        all_wellness[day.isoformat()] = wellness
        all_activities.extend(activities)

        if dry_run:
            print(wellness_to_md(day, wellness))
            for a in activities:
                print(activity_to_md(a))

    if dry_run:
        print("Dry run complete — no files written.")
        return

    if sink == "files":
        daily_dir = out / "daily"
        acts_dir = out / "activities"
        daily_dir.mkdir(parents=True, exist_ok=True)
        acts_dir.mkdir(parents=True, exist_ok=True)

        for ds, w in all_wellness.items():
            (daily_dir / f"{ds}.md").write_text(wellness_to_md(date.fromisoformat(ds), w))

        for a in all_activities:
            start = (a.get("startTimeLocal") or "unknown")[:10]
            name = a.get("activityName", "activity").replace(" ", "-").lower()
            filename = f"{start}-{name}.md"
            (acts_dir / filename).write_text(activity_to_md(a))

        data_file = out / "data.json"
        data_file.write_text(json.dumps({"wellness": all_wellness, "activities": all_activities}, indent=2))
        print(f"Written to {out}/")

    elif sink == "supabase":
        import urllib.request
        url = os.environ.get("GARMIN_INGEST_URL", "")
        secret = os.environ.get("GARMIN_INGEST_SECRET", "")
        if not url:
            sys.exit("Set GARMIN_INGEST_URL to use --sink supabase.")
        payload = json.dumps({"wellness": all_wellness, "activities": all_activities}).encode()
        req = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
        })
        urllib.request.urlopen(req)
        print("Posted to", url)


def main():
    parser = argparse.ArgumentParser(description="Sync Garmin data to files or a database.")
    parser.add_argument("--login", action="store_true", help="Log in and save token.")
    parser.add_argument("--days", type=int, default=1, help="How many days back to fetch.")
    parser.add_argument("--sink", choices=["files", "supabase"], default="files")
    parser.add_argument("--out", type=Path, default=Path("garmin"), help="Output folder (files sink).")
    parser.add_argument("--dry-run", action="store_true", help="Print output, write nothing.")
    args = parser.parse_args()

    if args.login:
        do_login()
    else:
        sync(args.days, args.sink, args.out, args.dry_run)


if __name__ == "__main__":
    main()
