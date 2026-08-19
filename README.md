# Train Seat Availability Bot

A production‑ready Telegram bot that checks Indian Railways seat availability for **all possible boarding stations** before a given destination.

---

## Features
- Conversational flow: train number → journey date → destination.
- Fetches complete train route, finds every station before the destination.
- Checks availability (SL, 3A, 2A, 1A, CC, 2S, EC, 3E) from each boarding station.
- Shows results grouped by boarding station, highlights the best option.
- Async HTTP calls, rate‑limited, retries with exponential back‑off.
- Config via `.env`; no secrets in code.
- Deployable on Render (worker service) using Docker.

---

## Project Structure
```
train-seat-bot/
├── main.py                # Entry point, starts polling
├── handlers.py            # Telegram conversation handlers
├── railway_api.py         # Railway API client (replaceable)
├── config.py              # Settings loaded from .env
├── utils.py               # Formatting & ranking helpers
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── render.yaml
└── README.md
```

---

## Local Development

1. **Clone & enter directory**
   ```bash
   git clone <repo>
   cd train-seat-bot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and fill:
   # BOT_TOKEN=your_telegram_bot_token
   # RAILWAY_API_KEY=your_railway_api_key
   # RAILWAY_API_BASE_URL=https://api.railwayapi.com/v2
   # DEFAULT_QUOTA=GN
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

6. **Test in Telegram** – send `/start` to your bot.

---

## Docker (local)

```bash
docker build -t train-seat-bot .
docker run --env-file .env train-seat-bot
```

---

## Deploy to Render

1. Push the repo to GitHub/GitLab.
2. In Render dashboard → **New +** → **Worker Service** → connect repo.
3. Render will detect `render.yaml` and `Dockerfile`.
4. Add the following **Environment Variables** (secret):
   - `BOT_TOKEN`
   - `RAILWAY_API_KEY`
   - `RAILWAY_API_BASE_URL` (optional, defaults)
   - `DEFAULT_QUOTA` (optional)
5. Deploy. Render will run the container as a long‑running worker (polling).

> Render worker services do not need an exposed HTTP port; the bot runs via Telegram long polling.

---

## Railway API Provider

The bot expects a REST API with these endpoints (example: `https://api.railwayapi.com/v2`):

| Function | Endpoint | Query Params |
|----------|----------|--------------|
| Train schedule | `/train` | `train=<number>` |
| Station lookup | `/station` | `station=<code_or_name>` |
| Availability | `/availability` | `train`, `source`, `dest`, `date`, `class`, `quota` |

Response must contain `response_code` = 200 on success. Adjust `railway_api.py` if your provider differs.

**Important:** Use a legitimate, authorized railway data API. Do **not** scrape IRCTC or bypass CAPTCHA.

---

## Commands
| Command | Description |
|---------|-------------|
| `/start` | Show main menu |
| `/help`  | Show usage guide |
| `/cancel`| Abort current flow |
| `/about` | (optional) Bot info |

---

## Logging
Logs are written to stdout (Docker‑friendly). No tokens or API keys are logged.

---

## Security Checklist
- All secrets via environment variables (`.env` not committed).
- Input validation on each step.
- API timeout (10 s) and retry with back‑off.
- Concurrency limited (5 parallel requests).
- Per‑user conversation isolation.

---

## Extending / Customising
- Add more classes in `utils.CLASS_ORDER`.
- Change quota default in `.env`.
- Replace `railway_api.py` with another provider – handlers stay unchanged.

---

## License
MIT – feel free to use and modify.