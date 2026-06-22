# Telegram Assignment Submission & Rewards Bot

This project implements a Telegram bot that:
- Accepts image and video submissions from students
- Forwards submissions to a configured channel
- Credits student balances based on configured pricing rules
- Tracks submission history and withdrawal requests in SQLite

Setup
1. Copy `.env.example` to `.env` and fill `BOT_TOKEN`, `CHANNEL_ID`, and `ADMIN_ID`.
2. Install dependencies:
```
pip install -r requirements.txt
```
3. Run the bot:
```
python bot.py
```

Notes
- Media groups are buffered for `MEDIA_GROUP_DELAY` seconds to ensure counting.
- Image tiers: >=3 => 3000 ETB, >=10 => 5000 ETB, >=20 => 8000 ETB.
- Video tiers by duration (seconds): <=60 => 2000 ETB, <=120 => 5000 ETB, <=180 => 10000 ETB.
- Withdrawals are enabled only at balances >= 50,000 ETB; admin is notified and handles payouts manually.

Deployment
- Use a VPS (DigitalOcean, Linode, etc.) and run with a process manager like `systemd` or `supervisor`.

Quick options to make the bot live using GitHub (repo name: `tbtbfx-create`)

1) Using Docker on a VPS (recommended)
- Push this repo to GitHub as `tbtbfx-create`.
- On your VPS, create SSH keys and add them to GitHub Actions secrets (`SSH_HOST`, `SSH_USER`, `SSH_KEY`, `REMOTE_DIR`).
- The included GitHub Actions workflow (`.github/workflows/deploy.yml`) will SSH into your VPS and run `docker compose up -d --build` on push to `main`.

2) Using systemd (manual deploy)
- Copy the repo to `/opt/tbtbfx-create` on your VPS.
- Edit `deploy/bot.service` to set `WorkingDirectory` and `Environment` variables.
- Enable and start the service:

```bash
sudo cp deploy/bot.service /etc/systemd/system/tbtbfx-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now tbtbfx-bot.service
```

3) Local testing
- Set environment variables and run:

```bash
export BOT_TOKEN=your_token
export CHANNEL_ID=-1004338526659
export ADMIN_ID=7856418550
python bot.py
```

Notes
- Add the repository name `tbtbfx-create` when creating the GitHub repo. The workflow assumes the remote will be pulled into `REMOTE_DIR` on your server.
- The workflow requires the remote server to have Docker and Docker Compose installed and a user that can run Docker commands.
