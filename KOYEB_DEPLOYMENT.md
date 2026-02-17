# Koyeb Deployment Guide

## Quick Setup

### 1. Environment Variables
Add these in Koyeb dashboard under "Environment variables":

```
DISCORD_TOKEN=your_bot_token_here
```

### 2. Deployment Settings

**In Koyeb Dashboard:**

- **Repository**: `https://github.com/KakashiCK440/bot_Discord`
- **Branch**: `main`
- **Build command**: (leave empty - auto-detected)
- **Run command**: `python bot.py`
- **Port**: `8080` (or whatever you set in `bot_config.py` as `WEB_SERVER_PORT`)
- **Health check path**: `/health`
- **Instance type**: Free tier is fine for small servers

### 3. Important Notes

✅ **What's Already Configured:**
- Web server for health checks (required by Koyeb)
- Procfile for worker process
- .gitignore excludes sensitive files
- Requirements.txt has all dependencies

⚠️ **Database Persistence:**
- Koyeb's free tier uses **ephemeral storage**
- Your database will reset on each deployment
- For production, consider:
  - Upgrading to persistent storage
  - Using external database (PostgreSQL)
  - Using cloud storage for SQLite file

### 4. Deployment Steps

1. **Push to GitHub** (already done ✅)
   ```bash
   git add .
   git commit -m "Ready for Koyeb deployment"
   git push origin main
   ```

2. **Create Koyeb App:**
   - Go to https://app.koyeb.com
   - Click "Create App"
   - Select "GitHub" as source
   - Choose your repository: `bot_Discord`
   - Select branch: `main`

3. **Configure Build:**
   - **Builder**: Buildpack
   - **Run command**: `python bot.py`
   - **Port**: `8080` (match your `WEB_SERVER_PORT`)
   - **Health check**: `/health`

4. **Add Environment Variables:**
   - Click "Environment variables"
   - Add `DISCORD_TOKEN` with your bot token

5. **Deploy:**
   - Click "Deploy"
   - Wait for build to complete (2-3 minutes)
   - Check logs for "✅ Bot is ready!"

### 5. Monitoring

**Check Logs:**
- Go to your app in Koyeb dashboard
- Click "Logs" tab
- Look for:
  - `✅ Logged in as YourBot`
  - `✅ Connected to X guilds`
  - `✅ Web server started on port 8080`

**Health Check:**
- Koyeb will ping `/health` endpoint
- If it fails, deployment will restart
- Check logs if restarts happen frequently

### 6. Updating Your Bot

After making changes:
```bash
git add .
git commit -m "Your update message"
git push origin main
```

Koyeb will automatically redeploy!

### 7. Troubleshooting

**Bot not starting:**
- Check `DISCORD_TOKEN` is set correctly
- Check logs for errors
- Verify all dependencies in `requirements.txt`

**Database resets:**
- This is normal on free tier
- Upgrade to persistent storage or use external DB

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
Only set in Koyeb dashboard (never commit):
- `DISCORD_TOKEN` - Your bot token

## Support

If you encounter issues:
1. Check Koyeb logs first
2. Verify environment variables are set
3. Ensure GitHub repository is up to date
4. Check Discord bot token is valid
