import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

GOALS = """
- Run an 8K at an 8-9 minute per mile pace
- Increase HRV over time
- Increase VO2 max
- Maintain muscle mass through weight lifting
- Eat the right calorie amounts — including how much to eat on run days, rest days, and weight training days
- Eventually incorporate cycling
"""

def load_wellness(garmin_dir: Path, days: int = 3) -> str:
    today = date.today()
    notes = []
    for i in range(days):
        day = today - timedelta(days=i)
        f = garmin_dir / "daily" / f"{day.isoformat()}.md"
        if f.exists():
            notes.append(f.read_text())
    return "\n\n".join(notes) if notes else "No wellness data available."


def load_recent_activities(garmin_dir: Path, days: int = 3) -> str:
    today = date.today()
    notes = []
    acts_dir = garmin_dir / "activities"
    if not acts_dir.exists():
        return "No recent activities."
    for f in sorted(acts_dir.iterdir(), reverse=True):
        name = f.stem
        try:
            day = date.fromisoformat(name[:10])
            if (today - day).days <= days:
                notes.append(f.read_text())
        except ValueError:
            continue
    return "\n\n".join(notes) if notes else "No recent activities."


def call_claude(wellness: str, activities: str, api_key: str) -> str:
    import urllib.request

    prompt = f"""You are a personal endurance and strength coach. Based on the athlete's Garmin recovery data and recent workouts below, write a short daily training report.

## Athlete goals
{GOALS.strip()}

## Wellness data (last 3 days)
{wellness}

## Recent activities (last 3 days)
{activities}

## Your report should include:
1. **Recovery status** — is the athlete ready to train hard, moderately, or should they rest? Base this on HRV, sleep, body battery, stress, and training readiness scores.
2. **Today's training recommendation** — specific: type of session, duration, intensity. If a run, give target pace. If lifting, give guidance on intensity.
3. **Nutrition today** — estimated calorie target and protein target based on what today's training looks like. Distinguish run days vs lift days vs rest days.
4. **One thing to focus on this week** — based on trends in the data.

Keep the report concise — under 300 words. Write it like a coach texting an athlete, not a medical report.
"""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    return data["content"][0]["text"]


def send_email(report: str, resend_key: str, to_email: str):
    import urllib.request

    today = date.today().isoformat()
    body = json.dumps({
        "from": "Garmin Coach <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"Your training report — {today}",
        "text": report,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resend_key}",
        }
    )
    urllib.request.urlopen(req)
    print(f"Report emailed to {to_email}")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("REPORT_EMAIL", "will.oldham2@gmail.com")
    garmin_dir = Path(os.environ.get("GARMIN_OUT", "garmin"))

    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY")
    if not resend_key:
        sys.exit("Set RESEND_API_KEY")

    wellness = load_wellness(garmin_dir)
    activities = load_recent_activities(garmin_dir)

    print("Generating report...")
    report = call_claude(wellness, activities, api_key)
    print(report)

    send_email(report, resend_key, to_email)


if __name__ == "__main__":
    main()
