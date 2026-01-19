# 🚢 Vessel Monitor (Safi-Nador-Jorf)

An automated Business Intelligence (BI) and monitoring system for maritime traffic at the Moroccan ports of **Safi (03)**, **Nador (06)**, and **Jorf Lasfar (07)**. This tool tracks vessel turnaround times, provides real-time arrival alerts, and generates monthly performance analytics using the ANP API.

---

## ✨ Key Features

* **🔄 Automated Monitoring**: Scans the port situation every 30 minutes via GitHub Actions.
* **📊 KPI Tracking**: Automatically calculates hours spent at **Anchorage** (waiting) vs. **Berth** (docked).
* **🔔 Premium Alerts**: Sends detailed HTML emails for new vessels appearing with "PREVU" status.
* **📈 Monthly BI Reports**: Automatically generates performance summaries on the 1st of every month.
* **🛠️ Fault Tolerance**: Features "battle-ready" headers for API resilience, automated state backups, and JSON validation.

---

## ⚙️ How It Works

The system operates as a serverless state machine within GitHub Actions:

1. **Extraction**: Pulls live JSON data from the ANP API.
2. **Comparison**: Matches live data against `state.json` to detect changes.
3. **Detection**:
* **New Vessel**: Triggers an arrival alert email.
* **Status Change**: Updates internal timers for anchorage or berth.
* **Departure**: Calculates final durations and moves the record to `history.json`.


4. **Reporting**: Triggers a performance audit if the run mode is set to "report".

---

## 🚀 Installation & Setup

### 1. Repository Configuration

* Ensure `monitor.py` and the `.github/workflows/monitor.yml` files are in your repository.
* Enable **Read and write permissions** for the GitHub Actions Bot under **Settings > Actions > General** to allow the system to save data.

### 2. Configure GitHub Secrets

Add the following secrets under **Settings > Secrets and variables > Actions**:

| Secret | Description |
| --- | --- |
| `EMAIL_USER` | Your Gmail address (the sender). |
| `EMAIL_PASS` | Your Gmail App Password (16-digit code). |
| `EMAIL_TO` | The primary recipient for alerts and reports. |
| `EMAIL_TO_COLLEAGUE` | (Optional) Secondary recipient for Nador-specific alerts. |

---

## 📈 Performance Grading

The system evaluates every port call using the following logic:

* **⭐ Excellent**: Anchorage < 5h and Berth < 24h.
* **✅ Bon**: Anchorage < 10h and Berth < 36h.
* **⚠️ Modéré**: Waiting time (anchorage) exceeds 10h.
* **🐌 Lent**: Significant delays in anchorage or operations.

---

## 🛡️ Resilience Features

* **Auto-Recovery**: Restores from `state.json.backup` if the primary state file is corrupted.
* **Ghost Ship Protection**: Keeps vessels in the system for 3 days if they disappear from the API without a "Completed" status, preventing data loss during API glitches.
* **Manual Triggers**: Use the **Actions** tab to manually run a `monitor` check or force a `report` generation at any time.

---

**Would you like me to help you configure the port codes for a different region, such as the Southern ports?**
