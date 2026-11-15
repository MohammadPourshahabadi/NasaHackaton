# Aboard website

The website version of Aboard. It shows the same rules, NASA baselines and local AI as the desktop app, running on one server so judges and visitors can try everything in a browser. No install or login.

## How it works

```
 Browser (phone or laptop)                 Aboard server (Google Cloud VM)
 ─────────────────────────                 ─────────────────────────────────────────────
 static/index.html, app.js  ── HTTPS ──▶   Caddy (automatic HTTPS for your domain)
   · Today, Trends, How it works                │
   · photos are read in the browser             ▼
     with Tesseract.js (text only is sent) server.py (plain Python, no extra packages)
                                              · reuses ../app: rules, NASA baselines, ai_core
                                              · demo crew Mo, Parisa, Nayan (simulated)
                                              · each visitor gets a private sandbox
                                                │
                                                ▼
                                           Ollama + Llama 3.2 3B (localhost only)
```

- **Rules decide the status.** The website calls the same `analysis.py`, `nasa_reference.py` and `baseline.py` as the desktop app.
- **The AI only reads and explains.** `/api/extract` turns a sentence into readings. `/api/explain` and `/api/ask` stream plain-language text as it is written.
- **Visitors can't break the demo.** New entries are kept per browser (a cookie) in memory, on top of the read-only demo history. Restarting the server resets them.
- **Nothing goes to an outside AI service.** Ollama listens only on the server itself.

## Run it on your own computer

You need Python 3.10+ with Pillow, plus Ollama with `llama3.2:3b` (see [../app/README.md](../app/README.md#turn-on-the-local-ai-optional)).

```bash
python website/server.py --port 8080
```

Open http://localhost:8080. Without Ollama, the site still works with offline rules.

## Put it online (Google Cloud + your domain)

This takes about 20 minutes. The Space Apps Google Cloud credits cover it.

### 1. Create the server
1. Activate the Google Cloud offer from the Space Apps **Global Offers** page, then open [console.cloud.google.com](https://console.cloud.google.com) and create a project.
2. Go to **Compute Engine → VM instances → Create instance**:
   - **Name:** `aboard`
   - **Region:** one close to you
   - **Machine type:** `e2-standard-4` (4 vCPU, 16 GB). A 3B model needs this much memory.
   - **Boot disk:** Ubuntu 24.04 LTS, **30 GB**
   - **Firewall:** tick **Allow HTTP traffic** and **Allow HTTPS traffic**
3. Click **Create**. Then go to **VPC network → IP addresses**, find the VM's external IP and click **Reserve** (make it static), so it never changes.

### 2. Install Aboard on it
Click **SSH** next to the VM. In the window that opens, run:

```bash
git clone https://github.com/MohammadPourshahabadi/NasaHackaton.git
cd NasaHackaton
sudo bash website/deploy/setup.sh yourdomain.com
```

Replace `yourdomain.com` with your domain. If you don't have one yet, leave it out and the site runs at `http://YOUR-IP`. The script installs Ollama, downloads Llama 3.2 (about 2 GB), starts the website as a service and sets up HTTPS. It takes about 5–10 minutes.

### 3. Point your domain at it (GoDaddy)
1. Activate the GoDaddy free domain offer and choose your domain.
2. In GoDaddy go to **My Products → your domain → DNS → Manage DNS**.
3. Edit the **A** record with name **@** so it points to your server's static IP. Delete any other `@` A records, such as GoDaddy's parking page.
4. Add a **CNAME** record with name **www** pointing to **@**.
5. Wait a few minutes, then open `https://yourdomain.com`. Caddy fetches the HTTPS certificate automatically on the first visit.

GoDaddy's free *website hosting* can't run Ollama. Use the domain only, and keep the site on the Google Cloud VM.

### 4. Before you submit
- Open the site in a private browser window and try **New entry**, **Ask me about your health** and **Trends**.
- Optional: request a [FortiGuard web filter classification](https://www.fortiguard.com/faq/wfratingsubmit) so judges' networks don't block a brand-new domain. Space Apps recommends this. Use the category "Education" and the company name "N/A".

### Useful commands (on the server)
| Task | Command |
| --- | --- |
| See live logs | `journalctl -u aboard-web -f` |
| Restart the site | `sudo systemctl restart aboard-web` |
| Update to the latest code | `cd ~/NasaHackaton && git pull && sudo systemctl restart aboard-web` |
| Check the AI | `curl localhost:8080/api/health` |

## Files

| File | Role |
| --- | --- |
| `server.py` | Web server and JSON API (`/api/today`, `/api/trends`, `/api/extract`, `/api/entry`, `/api/questionnaire`, `/api/explain`, `/api/ask`, `/api/health`) |
| `static/index.html`, `style.css`, `app.js` | The website |
| `static/img/` | Body-map illustrations (SI-generated, watermarked) |
| `deploy/setup.sh` | One-shot server setup: Ollama, model, service, HTTPS |

## SI and data disclosure
The anatomy illustrations are SI-generated and watermarked. Answers and explanations are written by a local language model (Llama 3.2 3B). The demo crew is simulated, drawn from NASA AP004/AP005 and Standard Measures distributions. This is a prototype, not a medical device.
