import os
import json
import re
import requests
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone 
from typing import Dict, List, Optional
from collections import defaultdict

# ==========================================
# ⚙️ CONFIGURATION & CONSTANTS
# ==========================================
TARGET_URL = "https://www.anp.org.ma/_vti_bin/WS/Service.svc/mvmnv/all"
STATE_FILE = "state.json" 
HISTORY_FILE = "history.json"
STATE_ENV_VAR = "VESSEL_STATE_DATA" 

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_TO_COLLEAGUE = os.getenv("EMAIL_TO_COLLEAGUE") 

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ENABLED = str(os.getenv("EMAIL_ENABLED", "true")).lower() == "true"
RUN_MODE = os.getenv("RUN_MODE", "monitor") 

# Target Ports: Safi (03), Nador (06), Jorf Lasfar (07)
ALLOWED_PORTS = {"03", "06", "07"} 

# Status categories for tracking
ANCHORAGE_STATUSES = {"EN RADE"}
BERTH_STATUSES = {"A QUAI"}
COMPLETED_STATUSES = {"APPAREILLAGE", "TERMINE"}
PLANNED_STATUSES = {"PREVU"}

# ==========================================
# 🚦 STATUS CLEANING (FIXED LOGIC)
# ==========================================
def clean_status(raw_status: str) -> str:
    """Sanitize and validate status from API"""
    if not raw_status: 
        return "UNKNOWN"
    
    status = raw_status.strip().upper()
    
    expected_statuses = {"PREVU", "EN RADE", "A QUAI", "APPAREILLAGE", "TERMINE"}
    if status not in expected_statuses:
        print(f"[WARNING] Unexpected API Status: '{raw_status}'")
    
    return status

# ==========================================
# 🌐 NETWORK RESILIENCE (BATTLE READY HEADERS)
# ==========================================
def fetch_vessel_data_with_retry(max_retries=3, initial_delay=5):
    """Fetch vessel data with full browser spoofing to bypass WAFs"""
    for attempt in range(max_retries):
        try:
            print(f"[INFO] Fetching vessel data (attempt {attempt + 1}/{max_retries})")
            
            # Upgraded headers to mimic a real browser session
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.anp.org.ma/',
                'Origin': 'https://www.anp.org.ma',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            resp = requests.get(TARGET_URL, timeout=(10, 60), headers=headers)
            resp.raise_for_status()
            
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError("API response is not a list")
                
            print(f"[SUCCESS] Fetched {len(data)} vessel records")
            return data
            
        except (requests.exceptions.RequestException, ValueError) as e:
            print(f"[WARNING] Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(initial_delay * (2 ** attempt))
            else:
                raise
    
    raise Exception("All retry attempts failed")

# ==========================================
# 💾 STATE MANAGEMENT (STABILITY UPGRADE)
# ==========================================
def load_state() -> Dict:
    """Load state with multi-source validation"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "active" in data and "history" in data:
                    return data
        except Exception as e:
            print(f"[WARNING] Local state load failed: {e}")
    
    state_data = os.getenv(STATE_ENV_VAR)
    if state_data:
        try:
            data = json.loads(state_data)
            if isinstance(data, dict) and "active" in data and "history" in data:
                return data
        except Exception:
            pass
    
    return {"active": {}, "history": []}

def save_state(state: Dict):
    """Save state with transactional backup logic"""
    try:
        if os.path.exists(STATE_FILE):
            import shutil
            shutil.copy2(STATE_FILE, f"{STATE_FILE}.backup")
        
        temp_file = f"{STATE_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_file, STATE_FILE)
    except Exception as e:
        print(f"[CRITICAL] State save failed: {e}")

# ==========================================
# 📅 DATE & TIME HELPERS
# ==========================================
def parse_ms_date(date_str: str) -> Optional[datetime]:
    if not date_str: return None
    m = re.search(r"/Date\((\d+)([+-]\d{4})?\)/", date_str)
    if m: 
        return datetime.fromtimestamp(int(m.group(1)) / 1000.0, tz=timezone.utc)
    return None

def fmt_dt(json_date: str) -> str:
    dt = parse_ms_date(json_date)
    if not dt: return "N/A"
    dt_m = dt.astimezone(timezone(timedelta(hours=1))) 
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    return f"{jours[dt_m.weekday()].capitalize()}, {dt_m.day:02d} {mois[dt_m.month-1]} {dt_m.year}"

def fmt_time_only(json_date: str) -> str:
    dt = parse_ms_date(json_date)
    if not dt: return "N/A"
    return dt.astimezone(timezone(timedelta(hours=1))).strftime("%H:%M")

def port_name(code: str) -> str:
    return {"03": "Safi", "06": "Nador", "07": "Jorf Lasfar"}.get(str(code), f"Port {code}")

# ==========================================
# 📊 ANALYTICS ENGINE
# ==========================================
def update_vessel_timers(active_vessel: Dict, new_status: str, now_utc: datetime) -> Dict:
    current_status = active_vessel.get("current_status", "UNKNOWN")
    last_updated_str = active_vessel.get("last_updated")
    
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            elapsed_hours = (now_utc - last_updated).total_seconds() / 3600.0
            
            if current_status in ANCHORAGE_STATUSES:
                active_vessel["anchorage_hours"] = active_vessel.get("anchorage_hours", 0.0) + elapsed_hours
            elif current_status in BERTH_STATUSES:
                active_vessel["berth_hours"] = active_vessel.get("berth_hours", 0.0) + elapsed_hours
        except Exception:
            pass 
    
    active_vessel["current_status"] = new_status
    active_vessel["last_updated"] = now_utc.isoformat()
    active_vessel["last_seen"] = now_utc.isoformat()
    return active_vessel

def calculate_performance_note(avg_anchorage: float, avg_berth: float) -> str:
    if avg_anchorage < 5 and avg_berth < 24: return "⭐ Excellent - Opérations rapides"
    if avg_anchorage < 10 and avg_berth < 36: return "✅ Bon - Efficace"
    if avg_anchorage < 24: return "⚠️ Modéré - Certaines attentes"
    return "🐌 Lent - Longues périodes d'attente"

# ==========================================
# 📧 EMAIL TEMPLATES (PREMIUM UI)
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
    <div style="font-family: Arial, sans-serif; margin: 15px 0; border:1px solid #d0d7e1; border-radius: 8px; overflow: hidden;">
        <div style="background: #0a3d62; color: white; padding: 12px; font-size: 16px;">🚢 <b>{nom}</b></div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr><td style="padding: 10px; border-bottom:1px solid #eeeeee; width: 30%;"><b>🕒 ETA</b></td><td style="padding: 10px; border-bottom:1px solid #eeeeee;">{eta_line}</td></tr>
            <tr><td style="padding: 10px; border-bottom:1px solid #eeeeee;"><b>🆔 IMO</b></td><td style="padding: 10px; border-bottom:1px solid #eeeeee;">{imo}</td></tr>
            <tr><td style="padding: 10px; border-bottom:1px solid #eeeeee;"><b>⚓ Escale</b></td><td style="padding: 10px; border-bottom:1px solid #eeeeee;">{escale}</td></tr>
            <tr><td style="padding: 10px; border-bottom:1px solid #eeeeee;"><b>🛳️ Type</b></td><td style="padding: 10px; border-bottom:1px solid #eeeeee;">{type_nav}</td></tr>
            <tr><td style="padding: 10px; border-bottom:1px solid #eeeeee;"><b>🏢 Agent</b></td><td style="padding: 10px; border-bottom:1px solid #eeeeee;">{cons}</td></tr>
            <tr><td style="padding: 10px;"><b>🌍 Prov.</b></td><td style="padding: 10px;">{prov}</td></tr>
        </table>
    </div>"""

def send_monthly_report(history: list, specific_port: str):
    if not history: return

    # MATH STABILITY: Pre-calculate to avoid f-string crashes
    total_calls = len(history)
    total_anch = sum(h.get('anchorage_hours', 0) for h in history)
    total_berth = sum(h.get('berth_hours', 0) for h in history)
    
    avg_anch = round(total_anch / total_calls, 1) if total_calls > 0 else 0
    avg_berth = round(total_berth / total_calls, 1) if total_calls > 0 else 0
    avg_total = round(avg_anch + avg_berth, 1)

    agent_stats = defaultdict(lambda: {"calls": 0, "total_anch": 0.0, "total_berth": 0.0})
    for h in history:
        agent = h.get('agent', 'Inconnu')
        agent_stats[agent]["calls"] += 1
        agent_stats[agent]["total_anch"] += h.get('anchorage_hours', 0)
        agent_stats[agent]["total_berth"] += h.get('berth_hours', 0)

    agent_rows = ""
    for agent, data in sorted(agent_stats.items(), key=lambda x: x[1]['calls'], reverse=True):
        a_anch = round(data['total_anch'] / data['calls'], 1) if data['calls'] > 0 else 0
        a_berth = round(data['total_berth'] / data['calls'], 1) if data['calls'] > 0 else 0
        note = calculate_performance_note(a_anch, a_berth)
        a_color = "#e74c3c" if a_anch > 12 else "#27ae60"
        b_color = "#f39c12" if a_berth > 36 else "#27ae60"
        
        agent_rows += f"""
        <tr style="border-bottom:1px solid #e0e0e0;">
            <td style="padding: 10px; font-weight: bold;">{agent}</td>
            <td style="padding: 10px; text-align: center;">{data['calls']}</td>
            <td style="padding: 10px; text-align: center; color: {a_color};">{a_anch}h</td>
            <td style="padding: 10px; text-align: center; color: {b_color};">{a_berth}h</td>
            <td style="padding: 10px; text-align: center; font-size: 12px;">{note}</td>
        </tr>"""

    vessel_rows = ""
    for h in sorted(history, key=lambda x: x.get('departure', ''), reverse=True):
        anch, berth = round(h.get('anchorage_hours', 0), 1), round(h.get('berth_hours', 0), 1)
        vessel_rows += f"""
        <tr style="border-bottom:1px solid #f0f0f0;">
            <td style="padding: 8px; font-weight: bold;">{h['vessel']}</td>
            <td style="padding: 8px;">{h.get('agent', '-')}</td>
            <td style="padding: 8px; text-align: center;">{anch}h</td>
            <td style="padding: 8px; text-align: center;">{berth}h</td>
            <td style="padding: 8px; text-align: center; font-weight: bold;">{round(anch+berth, 1)}h</td>
        </tr>"""

    subject = f"📊 Rapport Mensuel BI : Port de {specific_port} ({total_calls} Escales)"
    body = f"""
    <div style="font-family: Arial; max-width: 1100px; margin: auto;">
        <div style="background: linear-gradient(135deg, #0a3d62 0%, #1e5799 100%); color: white; padding: 20px; border-radius: 10px 10px 0 0;">
            <h2 style="margin: 0;">📊 Business Intelligence Report - {specific_port}</h2>
            <p>{total_calls} escales complétées | Données au {datetime.now().strftime('%d/%m/%Y')}</p>
        </div>
        <div style="background: #f8f9fa; padding: 25px; border:1px solid #d0d7e1; border-top: none; border-radius: 0 0 10px 10px;">
            <div style="margin-bottom: 30px; padding: 15px; background: #e8f4fc; border-left: 4px solid #3498db;">
                <h3 style="margin: 0; color: #2980b9;">📈 KPIs Clés du Port</h3>
                <p><b>Attente Moy.:</b> {avg_anch}h | <b>Quai Moy.:</b> {avg_berth}h | <b>Total Moy.:</b> {avg_total}h</p>
            </div>
            <h3 style="color: #0a3d62; border-bottom: 2px solid #0a3d62;">🏢 Performance des Agents</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; margin-bottom: 30px;">
                <tr style="background: #2c3e50; color: white;"><th>Agent</th><th>Escales</th><th>Attente</th><th>Quai</th><th>Note</th></tr>
                {agent_rows}
            </table>
            <h3 style="color: #0a3d62; border-bottom: 2px solid #0a3d62;">📋 Statistiques Navires</h3>
            <table style="width: 100%; border-collapse: collapse; background: white; font-size: 13px;">
                <tr style="background: #ecf0f1;"><th>Navire</th><th>Agent</th><th>Attente</th><th>Quai</th><th>Total</th></tr>
                {vessel_rows}
            </table>
        </div>
    </div>"""
    send_email(EMAIL_TO, subject, body)
    if specific_port == "Nador" and EMAIL_TO_COLLEAGUE: # Specific to monitor (3)
        send_email(EMAIL_TO_COLLEAGUE, subject, body)

def send_email(to, sub, body):
    if not EMAIL_ENABLED or not EMAIL_USER: return
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = sub, EMAIL_USER, to
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, [to], msg.as_string())
        print(f"[SUCCESS] Email sent to {to}")
    except Exception as e:
        print(f"[ERROR] Email failed: {e}")

# ==========================================
# 🔄 MAIN PROCESS (BATTLE READY)
# ==========================================
def main():
    print(f"{'='*50}\n🚢 VESSEL MONITOR - Battle Ready Edition\n{'='*50}")
    print(f"MODE: {RUN_MODE.upper()}\nPorts: Safi (03), Nador (06), Jorf Lasfar (07)")
    
    state = load_state()
    active, history = state.get("active", {}), state.get("history", [])

    if RUN_MODE == "report":
        for p_code in ALLOWED_PORTS:
            p_name = port_name(p_code)
            p_hist = [h for h in history if h.get("port") == p_name]
            if p_hist: send_monthly_report(p_hist, p_name)
        
        # Archive and Cleanup
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    old = json.load(f)
                    if isinstance(old, list): history = old + history
            except: pass
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        
        state["history"] = []
        save_state(state)
        print("[LOG] Monthly reports and archiving completed.")
        return

    try:
        all_data = fetch_vessel_data_with_retry()
    except Exception as e:
        print(f"[CRITICAL] API Failure: {e}")
        return

    now_utc = datetime.now(timezone.utc)
    live_vessels = {}
    
    for e in all_data:
        port_code = str(e.get("cODE_SOCIETEField", ""))
        if port_code in ALLOWED_PORTS:
            # FIXED: Sanitize status
            status = clean_status(e.get("sITUATIONField"))
            v_id = f"{e.get('nUMERO_LLOYDField','0')}-{e.get('nUMERO_ESCALEField','0')}"
            live_vessels[v_id] = {"e": e, "status": status}

    alerts, to_remove = {}, []
    
    # ==========================================
    # 🔍 MAIN TRACKING LOOP (PATCHED LOGIC)
    # ==========================================
    for v_id, stored in active.items():
        live = live_vessels.get(v_id)
        if live:
            # 1. Update timers based on time elapsed since last check
            stored = update_vessel_timers(stored, live["status"], now_utc)
            
            # 2. Universal Completion Logic
            # Triggers history for ANY ship entering a completed state (APPAREILLAGE/TERMINE)
            # regardless of whether it was at Quai or Anchorage previously.
            if live["status"] in COMPLETED_STATUSES:
                history.append({
                    "vessel": stored["entry"].get('nOM_NAVIREField', 'Unknown'),
                    "agent": stored["entry"].get("cONSIGNATAIREField", "Inconnu"),
                    "port": port_name(stored["entry"].get('cODE_SOCIETEField')),
                    "anchorage_hours": round(stored.get("anchorage_hours", 0.0), 1),
                    "berth_hours": round(stored.get("berth_hours", 0.0), 1),
                    "arrival": stored.get("first_seen", now_utc.isoformat()),
                    "departure": now_utc.isoformat()
                })
                to_remove.append(v_id)
            
            stored["entry"] = live["e"]
        else:
            # 3. Ghost Ship Fix
            # If vessel disappears from API, DO NOT update timers (prevents time inflation).
            # Only update last_seen to keep it in state for a few hours in case of API glitches.
            # Eventually the cleanup logic (below) will remove it after 3 days.
            stored["last_seen"] = now_utc.isoformat()
    
    # Remove ships that have completed their cycle
    for vid in to_remove: active.pop(vid, None)

    # ==========================================
    # ➕ NEW ARRIVALS
    # ==========================================
    for v_id, live in live_vessels.items():
        if v_id not in active:
            # First-run safety: Don't alert for ships already docked on startup
            if len(active) == 0 and live["status"] not in PLANNED_STATUSES: continue
            
            active[v_id] = {
                "entry": live["e"], "current_status": live["status"],
                "anchorage_hours": 0.0, "berth_hours": 0.0,
                "first_seen": now_utc.isoformat(), "last_updated": now_utc.isoformat(), "last_seen": now_utc.isoformat()
            }
            if live["status"] in PLANNED_STATUSES:
                p = port_name(live['e'].get("cODE_SOCIETEField"))
                alerts.setdefault(p, []).append(live["e"])

    # Final Cleanup and Save
    cutoff = now_utc - timedelta(days=3)
    state["active"] = {k: v for k, v in active.items() if datetime.fromisoformat(v.get("last_seen", now_utc.isoformat())).replace(tzinfo=timezone.utc) > cutoff}
    state["history"] = history[-1000:]
    save_state(state)

    if alerts:
        for p, vessels in alerts.items():
            names = ", ".join([v.get('nOM_NAVIREField', 'Unknown') for v in vessels])
            body = f"<p>Bonjour,<br>Mouvements prévus au Port de <b>{p}</b> :</p>" + "".join([format_vessel_details_premium(v) for v in vessels])
            send_email(EMAIL_TO, f"🔔 NOUVELLE ARRIVÉE | {names} au Port de {p}", body)
            if p == "Nador" and EMAIL_TO_COLLEAGUE: send_email(EMAIL_TO_COLLEAGUE, f"🔔 ARRIVÉE {names} | {p}", body)
    
    print(f"[STATS] Tracking {len(state['active'])} vessels | History: {len(history)}")

if __name__ == "__main__": main()
