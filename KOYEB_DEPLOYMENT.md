# Koyeb Deployment Guide

## Quick Setup

### 1. Database Setup (REQUIRED)

**⚠️ IMPORTANT**: You MUST set up a PostgreSQL database first, or your data will be wiped on every restart!

Follow the complete guide: **[DATABASE_SETUP.md](DATABASE_SETUP.md)**

Quick summary:
1. Create a free account at [Neon.tech](https://neon.tech)
2. Create a PostgreSQL database
3. Copy the connection string
4. Add it to Koyeb as `DATABASE_URL` environment variable

### 2. Environment Variables

Add these in Koyeb dashboard under "Environment variables":

**Required:**
```
DISCORD_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://username:password@host/database?sslmode=require
```

**Note**: The `DATABASE_URL` should be your Neon PostgreSQL connection string from [DATABASE_SETUP.md](DATABASE_SETUP.md)

**In Koyeb Dashboard:**

- **Repository**: `https://github.com/KakashiCK440/bot_Discord`
- **Branch**: `main`
- **Build command**: (leave empty - auto-detected)
- **Run command**: `python bot.py`
- **Port**: `8080` (or whatever you set in `bot_config.py` as `WEB_SERVER_PORT`)
- **Health check path**: `/health`
- **Instance type**: Free tier is fine for small servers

### 4. Important Notes

✅ **What's Already Configured:**
- Web server for health checks (required by Koyeb)
- Procfile for worker process
- .gitignore excludes sensitive files
- Requirements.txt has all dependencies
- PostgreSQL database support with automatic SQLite fallback for local development

✅ **Database Persistence:**
- Your bot now uses PostgreSQL for persistent storage
- Data will NOT be lost on restarts (as long as DATABASE_URL is set)
- Local development automatically uses SQLite
- See [DATABASE_SETUP.md](DATABASE_SETUP.md) for setup instructions

### 5. Deployment Steps

1. **Set up Database** (if not done already):
   - Follow [DATABASE_SETUP.md](DATABASE_SETUP.md) to create your Neon PostgreSQL database
   - Get your connection string

2. **Push to GitHub** (already done ✅)
   ```bash
   git add .
   git commit -m "Ready for Koyeb deployment"
   git push origin main
   ```

3. **Create Koyeb App:**
   - Go to https://app.koyeb.com
   - Click "Create App"
   - Select "GitHub" as source
   - Choose your repository: `bot_Discord`
   - Select branch: `main`

4. **Configure Build:**
   - **Builder**: Buildpack
   - **Run command**: `python bot.py`
   - **Port**: `8080` (match your `WEB_SERVER_PORT`)
   - **Health check**: `/health`

5. **Add Environment Variables:**
   - Click "Environment variables"
   - Add `DISCORD_TOKEN` with your bot token
   - Add `DATABASE_URL` with your Neon connection string (from DATABASE_SETUP.md)

6. **Deploy:**
   - Click "Deploy"
   - Wait for build to complete (2-3 minutes)
   - Check logs for:
     - `✅ Logged in as YourBot`
     - `🐘 Using PostgreSQL database`
     - `✅ PostgreSQL connection pool created`

### 6. Monitoring

**Check Logs:**
- Go to your app in Koyeb dashboard
- Click "Logs" tab
- Look for:
  - `✅ Logged in as YourBot`
  - `✅ Connected to X guilds`
  - `🐘 Using PostgreSQL database`
  - `✅ PostgreSQL connection pool created`
  - `✅ Web server started on port 8080`

**Health Check:**
- Koyeb will ping `/health` endpoint
- If it fails, deployment will restart
- Check logs if restarts happen frequently

### 7. Updating Your Bot

After making changes:
```bash
git add .
git commit -m "Your update message"
git push origin main
```

Koyeb will automatically redeploy!

### 8. Troubleshooting

**Bot not starting:**
- Check `DISCORD_TOKEN` is set correctly
- Check `DATABASE_URL` is set correctly
- Check logs for errors
- Verify all dependencies in `requirements.txt`

**Database connection errors:**
- Verify `DATABASE_URL` is set in Koyeb environment variables
- Check Neon database is active (free tier auto-sleeps after inactivity)
- Ensure connection string includes `?sslmode=require`
- See [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed troubleshooting

**Data still getting wiped:**
- Verify logs show `🐘 Using PostgreSQL database` (not SQLite)
- If you see `📁 Using SQLite database`, the `DATABASE_URL` is not set correctly
- Double-check the environment variable name is exactly `DATABASE_URL`

**Health check failing:**
- Verify `WEB_SERVER_PORT` matches Koyeb port setting
- Check web server is starting (look for log message)

## Configuration Files

### bot_config.py
Make sure `WEB_SERVER_PORT` is set to `8080` (Koyeb default):
```python
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))
```

### Environment Variables
Set in Koyeb dashboard (never commit):
- `DISCORD_TOKEN` - Your bot token
- `DATABASE_URL` - Your Neon PostgreSQL connection string (see [DATABASE_SETUP.md](DATABASE_SETUP.md))

## Support

If you encounter issues:
1. Check Koyeb logs first
2. Verify environment variables are set
3. Ensure GitHub repository is up to date
4. Check Discord bot token is valid
