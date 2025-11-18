#!/usr/bin/env python3 import os, sys, json, re, subprocess from datetime import datetime from dateutil import parser import pytz

#!/usr/bin/env python3 import os, sys, json, re, subprocess from datetime import datetime from dateutil import parser import pytz

Config
event_path = os.environ.get("GITHUB_EVENT_PATH") repo = os.environ.get("REPO") base_path = os.environ.get("TIME_TRACKER_PATH", ".github/time-tracker") tz_name = os.environ.get("TZ", "UTC") tz = pytz.timezone(tz_name)

if not event_path or not os.path.exists(event_path): print("No GITHUB_EVENT_PATH available") sys.exit(1)

with open(event_path, "r", encoding="utf-8") as f: ev = json.load(f)

comment_body = ev["comment"]["body"] comment_author = ev["comment"]["user"]["login"] issue_number = ev["issue"]["number"] timestamp = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(tz).isoformat()

Ensure directories
logs_dir = os.path.join(base_path, "logs") os.makedirs(logs_dir, exist_ok=True) log_file = os.path.join(logs_dir, f"issue-{issue_number}.json")

Load existing log for this issue
if os.path.exists(log_file): with open(log_file, "r", encoding="utf-8") as f: log = json.load(f) else: log = {"issue": issue_number, "entries": []}

Simple command parsing
cmd_match = re.match(r"^\s*/(\w+)(?:\s+(.+))?\s*$", comment_body.strip(), re.I) if not cmd_match: print("No command detected") sys.exit(0)

cmd = cmd_match.group(1).lower() args = (cmd_match.group(2) or "").strip()

entry = {"cmd": cmd, "args": args, "user": comment_author, "time": timestamp}

if cmd == "start": # start a task timing entry entry["type"] = "start" log["entries"].append(entry) elif cmd == "stop": entry["type"] = "stop" log["entries"].append(entry) elif cmd == "spent": # args: e.g. "25m" or "1h30m" or "90" entry["type"] = "spent" entry["raw"] = args # normalize to minutes mins = 0 m = re.findall(r"(\d+)\sm", args) h = re.findall(r"(\d+)\sh", args) if h: mins += int(h[0]) * 60 if m: mins += int(m[0]) if mins == 0: # try plain number try: mins = int(args) except: mins = None entry["minutes"] = mins log["entries"].append(entry) elif cmd == "pause": entry["type"] = "pause" log["entries"].append(entry) elif cmd == "resume": entry["type"] = "resume" log["entries"].append(entry) elif cmd == "note": entry["type"] = "note" entry["note"] = args log["entries"].append(entry) else: print(f"Comando no soportado: {cmd}") sys.exit(0)

Save log
with open(log_file, "w", encoding="utf-8") as f: json.dump(log, f, ensure_ascii=False, indent=2)

Commit changes
git_user = "github-actions[bot]" subprocess.run(["git", "config", "user.name", git_user], check=True) subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True) subprocess.run(["git", "add", log_file], check=True) subprocess.run(["git", "commit", "-m", f"Time-tracker: registro {cmd} en issue #{issue_number}"], check=False)

push with GITHUB_TOKEN
token = os.environ.get("GITHUB_TOKEN") if token: remote = f"https://x-access-token:{token}@github.com/{repo}.git" subprocess.run(["git", "push", remote, "HEAD:main"], check=False) else: print("No GITHUB_TOKEN, no se puede push")

print("Registro guardado.")

Script: .github/time-tracker/generate_daily_report.py
#!/usr/bin/env python3 import os, json, glob from datetime import datetime, date import pytz from dateutil import parser

base_path = os.environ.get("TIME_TRACKER_PATH", ".github/time-tracker") tz_name = os.environ.get("TZ", "UTC") tz = pytz.timezone(tz_name) today = datetime.now(tz).date() logs_dir = os.path.join(base_path, "logs") reports_dir = "reports" os.makedirs(reports_dir, exist_ok=True)

Collect logs
all_files = glob.glob(os.path.join(logs_dir, "issue-*.json")) report_lines = [] total_minutes = 0 tasks_count = 0

report_lines.append(f"# Reporte diario - {today.isoformat()}\n") report_lines.append(f"Generado: {datetime.now(tz).isoformat()}\n\n") report_lines.append("Resumen por issue:\n")

for fpath in all_files: with open(fpath, "r", encoding="utf-8") as f: data = json.load(f) issue = data.get("issue") entries = data.get("entries", []) # filter entries of today minutes_for_issue = 0 entries_for_today = [] for e in entries: try: t = parser.isoparse(e["time"]).astimezone(tz).date() except: continue if t == today: entries_for_today.append(e) if e.get("type") == "spent" and isinstance(e.get("minutes"), (int,float)): minutes_for_issue += e["minutes"] if not entries_for_today: continue tasks_count += 1 total_minutes += minutes_for_issue report_lines.append(f"## Issue #{issue}\n") report_lines.append(f"- Tiempo registrado hoy (min): {minutes_for_issue}\n") report_lines.append("- Acciones:\n") for e in entries_for_today: line = f" - [{e['time']}] {e['user']} -> {e['cmd']}" if e.get("args"): line += f" {e['args']}" if e.get("note"): line += f" — {e['note']}" report_lines.append(line + "\n") report_lines.append("\n")

Metrics
report_lines.append("## Métricas\n") report_lines.append(f"- Tarea(s) con actividad hoy: {tasks_count}\n") report_lines.append(f"- Tiempo total registrado (min): {total_minutes}\n") avg = (total_minutes / tasks_count) if tasks_count else 0 report_lines.append(f"- Tiempo promedio por tarea (min): {avg:.1f}\n")

Optional: jornada objetivo de 8h = 480 min
jornada = 480 pct = (total_minutes / jornada) * 100 report_lines.append(f"- Porcentaje jornada objetivo (asumiendo {jornada} min): {pct:.1f}%\n")

Save report
report_file = os.path.join(reports_dir, f"daily-{today.isoformat()}.md") with open(report_file, "w", encoding="utf-8") as f: f.writelines(line + ("\n" if not line.endswith("\n") else "") for line in report_lines)

Commit report
import subprocess repo = os.environ.get("REPO") subprocess.run(["git", "add", report_file], check=True) subprocess.run(["git", "commit", "-m", f"Time-tracker: report {today.isoformat()}"], check=False) token = os.environ.get("GITHUB_TOKEN") if token and repo: remote = f"https://x-access-token:{token}@github.com/{repo}.git" subprocess.run(["git", "push", remote, "HEAD:main"], check=False)

print("Reporte generado:", report_file)
