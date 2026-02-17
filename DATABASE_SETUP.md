# Database Setup Guide

This bot uses **PostgreSQL** for persistent data storage.

## Supabase Setup (Recommended)

### 1. Create a Supabase Project
1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Click "New Project"
3. Choose a name, database password, and region
4. Wait for the project to be created (~2 minutes)

### 2. Get Your Connection String
1. In your Supabase project dashboard, go to **Settings** → **Database**
2. Scroll down to **Connection String** section
3. Select **URI** tab
4. Copy the connection string (it looks like: `postgresql://postgres:[YOUR-PASSWORD]@db.xxx.supabase.co:5432/postgres`)
5. Replace `[YOUR-PASSWORD]` with your actual database password

### 3. Configure the Bot

#### Local Development
1. Open the `.env` file in the bot directory
2. Update the `DATABASE_URL`:
   ```
   DATABASE_URL=postgresql://postgres:your-password@db.xxx.supabase.co:5432/postgres
   ```

#### Koyeb Deployment
1. Go to your Koyeb dashboard
2. Select your bot service
3. Go to **Settings** → **Environment Variables**
4. Update `DATABASE_URL` with your Supabase connection string
5. Click **Save** and redeploy

## Database Tables

The bot will automatically create all necessary tables on first run:
- `players` - Player profiles and stats
- `player_weapons` - Player weapon selections
- `user_language` - User language preferences
- `server_settings` - Guild configuration
- `join_requests` - Join request tracking
- `server_join_settings` - Join system configuration
- `event_participants` - Event participation tracking

## Troubleshooting

### Connection Issues
- Ensure your connection string is correct
- Check that your database password doesn't contain special characters that need URL encoding
- Verify your IP is allowed (Supabase allows all IPs by default)

### Table Creation Errors
- The bot needs CREATE TABLE permissions
- Check Supabase logs in the dashboard for detailed errors

### Performance Issues
- Supabase free tier has connection limits
- Consider upgrading if you have a large server
