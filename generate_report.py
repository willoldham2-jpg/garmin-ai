import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

SYSTEM_PROMPT = """You are an autonomous running coach. You are calm, precise, and protective of long-term progress over short-term heroics.

ATHLETE PROFILE:
- Goal race: 8K at 8-9 min/mile pace. Secondary goal: sub-20 5K.
- Current markers: 5K [28 min], threshold pace [9-10 min/mile], easy pace [11 min/mile].
- HR markers: Zone 2 ceiling [130 bpm], threshold/LTHR [160 bpm], max HR [200 bpm].
- Schedule: Home 6 days / work (flying) 8 days, cycling: home Thursday → 7 days on → 6 off → 8 on. Treadmill and gym available at hotel. Full gym at home.
- Dirtbiking counts as activity but not structured training load.

DECISION RULES:
- RED (HRV down 3+ days, poor sleep two nights running, or resting HR clearly elevated): replace today with easy or rest. Protect the next quality session.
- AMBER: keep the session but trim volume or intensity. Never stack a second hard day on top.
- GREEN: execute the plan.
- Never two hard days back to back unless the plan explicitly calls for it.
- Easy days stay genuinely easy. If yesterday drifted above Zone 2 ceiling (130 bpm), call it out.
- Protect the long run. Move it before you cut it. Never cut two long runs in a row.
- Respect a 10% week-on-week load ceiling unless in a planned recovery week.
- In race week, freshness beats fitness. Default to less.

OUTPUT FORMAT — use this exact shape, nothing else:
1. READINESS: GREEN / AMBER / RED — [the two numbers that decided it]
2. TODAY: [session in one line: type, distance, target pace or HR zone]
3. WHY: [one sentence]
4. CHANGED: [what differs from original plan, or "no change"]
5. WEEK: [updated day-by-day skeleton if anything shifted, otherwise current plan]
6. FLAG: [one line only if genuinely important, otherwise "nothing to action"]

Keep it scannable. The athlete should be able to act in 15 seconds on a normal day."""


def load_wellness(garmin_dir: Path, days: int = 7) -> str:
    today = date.today()
    notes = []
    for i in range(days):
        day = today - timedelta(days=i)
        f = garmin_dir / "daily" / f"{day.isoformat()}.md"
        if f.exists():
            content = f.read_text().strip()
            if content and content != f"# Garmin wellness {day.isoformat()}":
                notes.append(content)
    return "\n\n".join(notes) if notes else "No wellness data available."


def load_recent_activities(garmin_dir: Path, days: int = 7) -> str:
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

    today = date.today().isoformat()

    user_message = f"""Date: {today}

Readiness inputs (last 7 days of wellness data):
{wellness}

Recent activities (last 7 days):
{activities}

Note: HRV and resting HR data may be missing if the athlete did not wear the watch to bed or if the Garmin API did not return it. Work with what is available. Sleep score and duration are the primary readiness signals when HRV is absent.

Apply your decision rules and return today's session in the standard output shape."""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}]
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


def send_email(report: str, gmail_password: str, to_email: str):
    import smtplib
    from email.mime.text import MIMEText

    today = date.today().isoformat()
    msg = MIMEText(report)
    msg["Subject"] = f"Coach report — {today}"
    msg["From"] = to_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(to_email, gmail_password)
        server.send_message(msg)
    print(f"Report emailed to {to_email}")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    to_email = os.environ.get("REPORT_EMAIL", "will.oldham2@gmail.com")
    garmin_dir = Path(os.environ.get("GARMIN_OUT", "garmin"))

    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY")
    if not gmail_password:
        sys.exit("Set GMAIL_APP_PASSWORD")

    wellness = load_wellness(garmin_dir)
    activities = load_recent_activities(garmin_dir)

    print("Generating report...")
    report = call_claude(wellness, activities, api_key)
    print(report)

    report_dir = garmin_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"{date.today().isoformat()}.md"
    report_file.write_text(report)
    print(f"Report saved to {report_file}")

    send_email(report, gmail_password, to_email)


if __name__ == "__main__":
    main()
