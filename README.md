
🚢 Vessel Monitor (Safi-Nador-Jorf)
A specialized Business Intelligence (BI) tool and automated tracking system for monitoring maritime traffic at the Moroccan ports of Safi (03), Nador (06), and Jorf Lasfar (07).

This system tracks vessel turnaround times (anchorage vs. berth), provides real-time arrival alerts, and generates monthly performance reports—all powered by GitHub Actions and the ANP (Agence Nationale des Ports) API.

✨ Key Features
🔄 Automated Monitoring: Runs every 30 minutes to track vessel status changes.

📊 KPI Tracking: Automatically calculates:

Anchorage Time: Hours spent waiting in the roads.

Berth Time: Hours spent docked for operations.

Agent Performance: Comparison of shipping agents' efficiency.

🔔 Premium Alerts: HTML-formatted email notifications for new vessel arrivals (PREVU status).

📈 Monthly BI Reports: Automated summaries sent on the 1st of every month featuring performance grades (⭐ Excellent to 🐌 Lent).

🛠️ Fault Tolerance: Includes automated state backups, JSON validation, and retry logic to handle API instability.

🏗️ Architecture
Workflow (monitor.yml): Orchestrates the environment, manages secrets, and handles data persistence by committing state.json and history.json back to the repository.

Engine (monitor.py):

Fetches data using a "battle-ready" header configuration to ensure API connectivity.

Manages vessel state transitions.

Calculates elapsed time using UTC timestamps to prevent inflation during API downtime.

Data Storage:

state.json: Current active vessels and timers.

history.json: Archived records of completed port calls.

🚀 Setup & Deployment
1. Prerequisites
A private or public GitHub Repository.

A Gmail account (or other SMTP service) for sending reports.

2. GitHub Secrets
Go to Settings > Secrets and variables > Actions and add the following:

Secret	Description
EMAIL_USER	Your email address (e.g., sender@gmail.com).
EMAIL_PASS	Your App Password (for Gmail, use App Passwords).
EMAIL_TO	Primary recipient of alerts and reports.
EMAIL_TO_COLLEAGUE	(Optional) Secondary recipient for Nador-specific alerts.
3. Permissions
Ensure the GitHub Actions Bot has write access to your repository:

Go to Settings > Actions > General.

Under Workflow permissions, select Read and write permissions.

📈 Monitoring & Reports
Performance Grading
The system automatically evaluates port calls based on the following logic:

⭐ Excellent: Anchorage < 5h AND Berth < 24h.

✅ Bon: Anchorage < 10h AND Berth < 36h.

⚠️ Modéré: Waiting time exceeds 10h.

🐌 Lent: Significant delays in anchorage or operations.

Manual Triggers
You can manually trigger the script via the Actions tab:

Select Vessel Monitor.

Click Run workflow.

Choose Mode:

monitor: Standard check for new arrivals and timer updates.

report: Force generate the monthly BI report immediately.

🛡️ Resilience Features
Auto-Recovery: If state.json is corrupted, the system attempts to restore from state.json.backup.

Conflict Handling: Uses git pull --rebase to handle concurrent workflow runs.

Ghost Ship Protection: Vessels that disappear from the API without a "Completed" status are kept in state for 3 days before cleanup to account for temporary API glitches.
