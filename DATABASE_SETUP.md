# Database Setup Guide - Neon PostgreSQL

This guide will help you set up a free PostgreSQL database with Neon to ensure your bot data persists across restarts on Koyeb.

## Why Do I Need This?

Koyeb uses **ephemeral storage**, meaning any files (including your SQLite database) are deleted when the bot restarts. By using a cloud PostgreSQL database, your data will be stored permanently.

## Step 1: Create a Neon Account

1. Go to [https://neon.tech](https://neon.tech)
2. Click **"Sign Up"** (you can use GitHub, Google, or email)
3. Verify your email if required

## Step 2: Create a PostgreSQL Database

1. After logging in, click **"Create Project"**
2. Fill in the details:
   - **Project name**: `discord-bot` (or any name you prefer)
   - **PostgreSQL version**: 16 (recommended)
   - **Region**: Choose the closest to your Koyeb deployment
     - US East (Ohio) for Washington D.C.
     - EU (Frankfurt) for Frankfurt
     - Asia Pacific (Singapore) for Singapore
3. Click **"Create Project"**

## Step 3: Get Your Connection String

1. After the project is created, you'll see a **Connection Details** section
2. Look for the **Connection string** dropdown
3. Select **"Pooled connection"** (recommended for better performance)
4. Copy the connection string - it looks like this:
   ```
   postgresql://username:password@ep-xxx-xxx.region.aws.neon.tech/dbname?sslmode=require
   ```
5. **IMPORTANT**: Save this connection string securely - you'll need it for Koyeb

## Step 4: Add DATABASE_URL to Koyeb

1. Go to your [Koyeb Dashboard](https://app.koyeb.com)
2. Click on your bot application
3. Click **"Settings"** → **"Environment variables"**
4. Click **"Add variable"**
5. Add the following:
   - **Name**: `DATABASE_URL`
   - **Value**: Paste your Neon connection string from Step 3
   - **Type**: Secret (recommended for security)
6. Click **"Save"**

## Step 5: Deploy Your Bot

### Option A: Automatic Deployment (if auto-deploy is enabled)

1. Push your code changes to GitHub:
   ```bash
   git add .
   git commit -m "Add PostgreSQL support"
   git push origin main
   ```
2. Koyeb will automatically redeploy your bot

### Option B: Manual Deployment

1. In Koyeb dashboard, click **"Redeploy"**
2. Wait for the deployment to complete (2-3 minutes)

## Step 6: Verify It's Working

1. Check the Koyeb logs:
   - Look for: `🐘 Using PostgreSQL database`
   - Look for: `✅ PostgreSQL connection pool created`
   - Look for: `✅ Database initialized`

2. Test your bot:
   - Create a player profile: `/createprofile`
   - Check it works: `/profile`

3. **Test persistence** (THE IMPORTANT PART):
   - In Koyeb dashboard, click **"Restart"** to restart your bot
   - Wait for it to come back online
   - Run `/profile` again
   - **Your profile should still be there!** ✅

## Troubleshooting

### Error: "PostgreSQL support not available"

**Solution**: Make sure `psycopg2-binary` is in your `requirements.txt`:
```
psycopg2-binary>=2.9.9
```

### Error: "Connection refused" or "Could not connect to server"

**Possible causes**:
1. **Wrong connection string**: Double-check you copied the entire string from Neon
2. **Missing sslmode**: Ensure your connection string ends with `?sslmode=require`
3. **Neon database sleeping**: Free tier databases auto-sleep after inactivity. The first connection might take a few seconds.

### Error: "password authentication failed"

**Solution**: Your connection string might be incorrect. Go back to Neon dashboard and copy a fresh connection string.

### Bot works but data still gets wiped

**Check**:
1. Verify `DATABASE_URL` is set in Koyeb environment variables
2. Check logs for `🐘 Using PostgreSQL database` - if you see `📁 Using SQLite database` instead, the environment variable isn't set correctly

## Local Development

Your bot will automatically use SQLite when running locally (no `DATABASE_URL` set). This is perfect for testing without affecting your production database.

To test with PostgreSQL locally:
1. Copy your Neon connection string
2. Create a `.env` file in your project:
   ```
   DATABASE_URL=postgresql://your-connection-string-here
   ```
3. Run your bot locally

## Neon Free Tier Limits

✅ **What you get for FREE**:
- 3 GB storage per branch
- 100 compute hours per month
- Unlimited databases
- Auto-scaling
- No credit card required

⚠️ **Limits**:
- If you exceed 100 compute hours/month, database will pause until next month
- For a Discord bot, this is usually more than enough

## Monitoring Your Database

1. Go to [Neon Dashboard](https://console.neon.tech)
2. Click on your project
3. View:
   - **Storage usage**: How much data you're storing
   - **Compute hours**: How many hours you've used this month
   - **Queries**: Recent database activity

## Need Help?

- **Neon Documentation**: https://neon.tech/docs
- **Neon Discord**: https://discord.gg/neon
- Check your bot logs in Koyeb for error messages
