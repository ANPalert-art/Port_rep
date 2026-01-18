Port line-up

🚢 ANP Vessel Monitor & Performance Reporter

An automated monitoring system that tracks vessel movements in Moroccan ports via the ANP (Agence Nationale des Ports) API. The system provides real-time email alerts for new arrivals and generates comprehensive monthly performance reports.
🌟 Key Features
 * Real-time Tracking: Scans the port situation every 30 minutes.
 * Premium Alerts: Sends detailed HTML emails for new "PREVU" (Expected) vessels.
 * Smart Transitions: Automatically calculates time spent at Anchorage vs. Quay.
 * Monthly Analytics: On the 1st of every month, generates a performance report including:
   * Total calls per Shipping Agent.
   * Average waiting times.
   * Detailed historical log of all movements.
 * Human-Mimicry: Uses custom headers to interact safely with the API.
 * 
⚙️ How It Works

The system operates using GitHub Actions (no server required) and a State Machine logic:
 * Extraction: Pulls JSON data from the ANP API.
 * Comparison: Compares "Live" data against state.json (the local memory).
 * Detection: * If a vessel is new \rightarrow Send Arrival Alert.
   * If a vessel departs \rightarrow Calculate Durations & Save to History.
 * Reporting: If the date is the 1st of the month, it triggers the report mode instead of monitor mode.
 * 
🚀 Installation & Setup

1. Repository Setup
 * Clone this repository or create a new one.
 * Ensure monitor.py and your .yml workflow file are in the correct folders.
2. Configure GitHub Secrets
To protect your credentials, go to Settings > Secrets and variables > Actions and add:
| Secret     |       Description           |
|------------|-----------------------------|
| EMAIL_USER | Your Gmail address (sender) |
| EMAIL_PASS | Your Gmail App Password (16 digits) |
| EMAIL_TO | The recipient email address |
3. Port Configuration
In monitor.py, update the TARGET_PORTS list with the codes for your region:
 * North: {"03", "06", "07"} (Safi, Nador, Jorf)
 * South: {"16", "17", "18"} (Tan Tan, Laâyoune, Dakhla)
 * 
🛠️ Technical Details

Workflow Schedule
 * Monitor Mode: */30 * * * * (Every 30 mins)
 * Report Mode: 0 8 1 * * (1st of month at 08:00 AM)
File Structure
 * monitor.py: The core Python logic (API calls, Email formatting).
 * state.json: The "database" file (created/updated automatically).
 * .github/workflows/vessel_monitor.yml: The automation engine.
 * 
📊 Monthly Report Preview

The report uses a Premium Blue design with a breakdown of agent performance:
 * Agent Name | Escales | Avg Waiting | Avg Working
 * 
📝 License

Distributed under the MIT License. Created for maritime logistics optimization.
 

