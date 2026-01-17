import os
import json
import re
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone 
from typing import Dict, List, Optional

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
TARGET_URL = "https://www.anp.org.ma/_vti_bin/WS/Service.svc/mvmnv/all"
STATE_FILE = "state.json" 
STATE_ENV_VAR = "VESSEL_STATE_DATA" 

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ENABLED = str(os.getenv("EMAIL_ENABLED", "true")).lower() == "true"
RUN_MODE = os.getenv("RUN_MODE", "monitor") 

# Ports: SAFI (03), NADOR (06), JORF LASFAR (07)
ALLOWED_PORTS = {"03", "06", "07"} 

# ==========================================
# 💾 STATE MANAGEMENT
# ==========================================
def load_state() -> Dict:
    """Loads state from file or environment variable."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass

    state_data = os.getenv(STATE_ENV_VAR)
    if not state_data: return {"active": {}, "history": []}
    try:
        data = json.loads(state_data)
        return data if "active" in data else {"active": {}, "history": []}
    except (json.JSONDecodeError, TypeError):
        return {"active": {}, "history": []}

def save_state(state: Dict):
    """Saves state to file."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[ERROR] Save failed: {e}")

# ==========================================
# 📅 DATE & TIME HELPERS
# ==========================================
def parse_ms_date(date_str: str) -> Optional[datetime]:
    """Parses Microsoft JSON date format /Date(timestamp)/."""
    if not date_str: return None
    m = re.search(r"/Date\((\d+)([+-]\d{4})?\)/", date_str)
    if m: 
        return datetime.fromtimestamp(int(m.group(1)) / 1000.0, tz=timezone.utc)
    return None

def fmt_dt(json_date: str) -> str:
    """Formats date into French localized string."""
    dt = parse_ms_date(json_date)
    if not dt: return "N/A"
    dt_m = dt.astimezone(timezone(timedelta(hours=1))) 
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{jours[dt_m.weekday()].capitalize()}, {dt_m.day:02d} {mois[dt_m.month-1]} {dt_m.year}"

def fmt_time_only(json_date: str) -> str:
    """Formats time into HH:MM."""
    dt = parse_ms_date(json_date)
    if not dt: return "N/A"
    return dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

def calculate_duration_hours(start_iso: str, end_dt: datetime) -> float:
    """Calculates hours difference between ISO string and datetime object."""
    try:
        start_dt = datetime.fromisoformat(start_iso)
        if start_dt.tzinfo is None: start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=timezone.utc)
        return (end_dt - start_dt).total_seconds() / 3600.0
    except: return 0.0

def port_name(code: str) -> str:
    return {"03": "Safi", "06": "Nador", "07": "Jorf Lasfar"}.get(str(code), f"Port {code}")

# ==========================================
# 📧 EMAIL TEMPLATES
# ==========================================
def format_vessel_details_premium(entry: dict) -> str:
    nom = entry.get("nOM_NAVIREField") or "INCONNU"
    imo = entry.get("nUMERO_LLOYDField") or "N/A"
    cons = entry.get("cONSIGNATAIREField") or "N/A"
    escale = entry.get("nUMERO_ESCALEField") or "N/A"
    eta_line = f"{fmt_dt(entry.get('dATE_SITUATIONField'))} {fmt_time_only(entry.get('hEURE_SITUATIONField'))}"
    prov = entry.get("pROVField") or "Inconnue"
    type_nav = entry.get("tYP_NAVIREField") or "N/A"

    return f"""
    <div style="font-family: Arial, sans-serif; margin: 15px 0; border: 1px solid #d0d7e1; border-radius: 8px; overflow: hidden;">
        <div style="background: #0a3d62; color: white; padding: 12px; font-size: 16px;">
            🚢 <b>{nom}</b>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee; width: 30%;"><b>🕒 ETA</b></td>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">{eta_line}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><b>🆔 IMO</b></td>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">{imo}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><b>⚓ Escale</b></td>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">{escale}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><b>🛳️ Type</b></td>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">{type_nav}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;"><b>🏢 Agent</b></td>
                <td style="padding: 10px; border-bottom: 1px solid #eeeeee;">{cons}</td>
            </tr>
            <tr>
                <td style="padding: 10px;"><b>🌍 Prov.</b></td>
                <td style="padding: 10px;">{prov}</td>
            </tr>
        </table>
    </div>"""

def send_monthly_report(history: list, specific_port: str):
    """Generates a performance report for a specific port."""
    if not history:
        return

    # 1. Process Data for Statistics
    stats = {}
    for h in history:
        agent = h.get('agent', 'Inconnu')
        quay_dur = h.get('duration', 0)
        anch_dur = h.get('anchorage_duration', 0)
        if agent not in stats: stats[agent] = {"calls": 0, "quay_sum": 0.0, "anch_sum": 0.0}
        stats[agent]["calls"] += 1
        stats[agent]["quay_sum"] += quay_dur
        stats[agent]["anch_sum"] += anch_dur

    # 2. Build Agent Stats Table
    agent_rows = ""
    sorted_agents = sorted(stats.items(), key=lambda x: x[1]['calls'], reverse=True)
    for agent, data in sorted_agents:
        total_calls = data['calls']
        avg_quay = round(data['quay_sum'] / total_calls, 1) if total_calls > 0 else 0
        avg_anch = round(data['anch_sum'] / total_calls, 1) if total_calls > 0 else 0
        agent_rows += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 10px; font-weight: bold; color: #333;">{agent}</td>
            <td style="padding: 10px; text-align: center; color: #333;">{total_calls}</td>
            <td style="padding: 10px; text-align: center; color: #333;">{avg_anch}h</td>
            <td style="padding: 10px; text-align: center; color: #333;">{avg_quay}h</td>
        </tr>"""

    # 3. Build Detailed Vessel List
    sorted_history = sorted(history, key=lambda x: x.get('departure', ''), reverse=True)
    vessel_rows = ""
    for h in sorted_history:
        try:
            dt = datetime.fromisoformat(h['departure'])
            dt_local = dt.astimezone(timezone(timedelta(hours=1)))
            date_str = dt_local.strftime("%d/%m/%Y %H:%M")
        except: date_str = "N/A"
        anch_val = h.get('anchorage_duration', 0)
        anch_str = f"{anch_val:.1f}h" if anch_val > 0 else "-"
        quay_str = f"{h.get('duration', 0):.1f}h"
        vessel_rows += f"""
        <tr style="border-bottom: 1px solid #f0f0f0;">
            <td style="padding: 8px; color: #333;">{h['vessel']}</td>
            <td style="padding: 8px; color: #333; font-size: 13px;">{h.get('agent', '-')}</td>
            <td style="padding: 8px; text-align: center; color: #555; font-size: 12px;">{anch_str}</td>
            <td style="padding: 8px; text-align: center; color: #555; font-size: 12px;">{quay_str}</td>
            <td style="padding: 8px; color: #555; font-size: 12px;">{date_str}</td>
        </tr>"""

    subject = f"📊 Rapport Mensuel : Port de {specific_port} ({len(history)} Mouvements)"
    body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 900px; margin: auto;">
        <div style="background: #0a3d62; color: white; padding: 15px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0; font-size: 20px;">📊 Rapport de Performance</h2>
            <p style="margin: 5px 0 0; opacity: 0.9; font-size: 14px;">Port de {specific_port} - Statistiques Mensuelles</p>
        </div>
        <div style="background: #f8f9fa; padding: 20px; border: 1px solid #d0d7e1; border-top: none; border-radius: 0 0 8px 8px;">
            <p>Bonjour,</p>
            <p>Voici le récapitulatif d'activité mensuel pour le <b>Port de {specific_port}</b>.</p>
            <h3 style="color: #0a3d62; margin-top: 0; border-bottom: 2px solid #0a3d62; padding-bottom: 10px;">🏢 Statistiques par Agent</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; margin-bottom: 30px; border-radius: 4px; overflow: hidden;">
                <thead><tr style="background: #e9ecef; text-align: left;">
                    <th style="padding: 12px; font-size: 13px; color: #495057;">Agent</th>
                    <th style="padding: 12px; font-size: 13px; color: #495057; text-align: center;">Escales</th>
                    <th style="padding: 12px; font-size: 13px; color: #495057; text-align: center;">⚓ Attente</th>
                    <th style="padding: 12px; font-size: 13px; color: #495057; text-align: center;">🏗️ Quai</th>
                </tr></thead>
                <tbody>{agent_rows}</tbody>
            </table>
            <h3 style="color: #0a3d62; border-bottom: 2px solid #0a3d62; padding-bottom: 10px;">📋 Liste Détaillée</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; font-size: 13px; border-radius: 4px; overflow: hidden;">
                <thead><tr style="background: #e9ecef; text-align: left;">
                    <th style="padding: 10px; color: #495057;">Navire</th>
                    <th style="padding: 10px; color: #495057;">Agent</th>
                    <th style="padding: 10px; color: #495057; text-align: center;">⚓ Poste</th>
                    <th style="padding: 10px; color: #495057; text-align: center;">🏗️ Quai</th>
                    <th style="padding: 10px; color: #495057;">Date</th>
                </tr></thead>
                <tbody>{vessel_rows}</tbody>
            </table>
            <div style='margin-top: 30px; border-top: 1px solid #e6e9ef; padding-top: 15px;'>
                <p style='font-size:14px; color:#333;'>Cordialement,</p>
                <p style='font-size:12px; color:#777777; font-style: italic;'>Rapport automatique.</p>
            </div>
        </div>
    </div>"""
    send_email(EMAIL_TO, subject, body)

def send_email(to, sub, body):
    if not EMAIL_ENABLED or not EMAIL_USER: return
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = sub, EMAIL_USER, to
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, [to], msg.as_string())
    except Exception as e:
        print(f"[ERROR] Email Error: {e}")

# ==========================================
# 🔄 MAIN PROCESS
# ==========================================
def main():
    print(f"{'='*30}\nMODE: {RUN_MODE.upper()}\n{'='*30}")
    state = load_state()
    active = state.get("active", {})
    history = state.get("history", [])

    # REPORT MODE
    if RUN_MODE == "report":
        print(f"[LOG] Generating monthly reports.")
        port_history = {"Safi": [], "Nador": [], "Jorf Lasfar": []}
        for h in history:
            p_name = h.get("port")
            if p_name in port_history: port_history[p_name].append(h)
        for port_name, p_hist in port_history.items():
            if p_hist:
                print(f"[LOG] Sending report for {port_name} ({len(p_hist)} movements).")
                send_monthly_report(p_hist, port_name)
        return

    # MONITOR MODE
    try:
        resp = requests.get(TARGET_URL, timeout=30)
        resp.raise_for_status()
        all_data = resp.json()
        print(f"[LOG] API Data Fetched: {len(all_data)} vessels.")
    except Exception as e:
        print(f"[CRITICAL] API Fetch Error: {e}")
        return

    now_utc = datetime.now(timezone.utc)
    live_vessels = {}
    
    for e in all_data:
        if str(e.get("cODE_SOCIETEField")) in ALLOWED_PORTS:
            imo = e.get('nUMERO_LLOYDField') or "0000000"
            esc = e.get('nUMERO_ESCALEField') or "0"
            v_id = f"{imo}-{esc}"
            live_vessels[v_id] = {"e": e, "status": (e.get("sITUATIONField") or "").upper()}

    alerts = {}
    to_remove = []

    # 2. Update Existing Vessels
    for v_id, stored in active.items():
        live = live_vessels.get(v_id)
        if live:
            prev_status = stored["status"]
            new_status = live["status"]
            
            # A. ANCHORAGE TRACKING
            if new_status == "ANCRE" and prev_status != "ANCRE":
                stored["anchored_at"] = now_utc.isoformat()
                print(f"[LOG] Anchorage detected: {stored['entry'].get('nOM_NAVIREField')}")

            # B. ARRIVAL TO QUAY
            if prev_status != "A QUAI" and new_status == "A QUAI":
                stored["quai_at"] = now_utc.isoformat()
                anchorage_duration = 0.0
                if "anchored_at" in stored:
                    anchorage_duration = calculate_duration_hours(stored["anchored_at"], now_utc)
                stored["anchorage_duration"] = anchorage_duration
                print(f"[LOG] Arrival at Quay: {stored['entry'].get('nOM_NAVIREField')} (Anchorage: {anchorage_duration}h)")
            
            # C. DEPARTURE
            if prev_status == "A QUAI" and new_status == "APPAREILLAGE":
                quai_time = stored.get("quai_at", stored["last_seen"])
                quay_duration = calculate_duration_hours(quai_time, now_utc)
                anchorage_duration = stored.get("anchorage_duration", 0.0)
                
                history.append({
                    "vessel": stored["entry"].get('nOM_NAVIREField'),
                    "agent": stored["entry"].get("cONSIGNATAIREField", "Inconnu"),
                    "port": port_name(stored["entry"].get('cODE_SOCIETEField')),
                    "duration": round(quay_duration, 2),
                    "anchorage_duration": round(anchorage_duration, 2),
                    "departure": now_utc.isoformat()
                })
                to_remove.append(v_id)
                print(f"[LOG] Departure: {stored['entry'].get('nOM_NAVIREField')} (Stay: {quay_duration:.2f}h)")
            
            stored["status"] = new_status
            stored["last_seen"] = now_utc.isoformat()

    for vid in to_remove: 
        active.pop(vid, None)

    # 4. Detect New Vessels (PREVU)
    for v_id, live in live_vessels.items():
        if v_id not in active:
            # --- FIRST RUN CLEAN START ---
            # If the state is empty (First Run), ignore vessels that are already in progress.
            # Only track Scheduled (PREVU) vessels to ensure we track the full cycle.
            if len(active) == 0 and live["status"] != "PREVU":
                print(f"[LOG] First Run: Ignoring existing active vessel {live['e'].get('nOM_NAVIREField')} ({live['status']})")
                continue
            # ----------------------------

            active[v_id] = {
                "entry": live["e"], 
                "status": live["status"], 
                "last_seen": now_utc.isoformat()
            }
            if live["status"] == "PREVU":
                p = port_name(live['e'].get("cODE_SOCIETEField"))
                alerts.setdefault(p, []).append(live["e"])

    # 5. Garbage Collection
    cutoff = now_utc - timedelta(days=3)
    state["active"] = {
        k: v for k, v in active.items() 
        if datetime.fromisoformat(v["last_seen"]).replace(tzinfo=timezone.utc) > cutoff
    }
    state["history"] = history[-100:] 
    save_state(state)

    # 6. Sending Alerts
    if alerts:
        for p, vessels in alerts.items():
            v_names = ", ".join([v.get('nOM_NAVIREField', 'Unknown') for v in vessels])
            intro = f"<p style='font-family:Arial; font-size:15px;'>Bonjour,<br><br>Ci-dessous les mouvements prévus au <b>Port de {p}</b> :</p>"
            cards = "".join([format_vessel_details_premium(v) for v in vessels])
            footer = f"""
            <div style='margin-top: 20px; border-top: 1px solid #e6e9ef; padding-top: 15px;'>
                <p style='font-family:Arial; font-size:14px; color:#333;'>Cordialement,</p>
                <p style='font-family:Arial; font-size:12px; color:#777777; font-style: italic;'>
                    Ceci est une génération automatique par le système de surveillance.
                </p>
            </div>"""
            full_body = intro + cards + footer
            new_subject = f"🔔 NOUVELLE ARRIVÉE PRÉVUE | {v_names} au Port de {p}"
            send_email(EMAIL_TO, new_subject, full_body)
            print(f"[EMAIL] Sent for {p}: {v_names}")
    else:
        print("[LOG] No new PREVU vessels detected.")

if __name__ == "__main__":
    main()
