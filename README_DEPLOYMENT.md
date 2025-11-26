# CKUI Support Assistant - Deployment Guide

## Backend Setup

### Local Development

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` file:
   ```bash
   cp .env.example .env
   ```

3. Add your Mistral API key to `.env`:
   ```
   MISTRAL_API_KEY=your-actual-api-key-here
   ```

4. Run the server:
   ```bash
   python server.py
   ```

5. Open `index.html` in your browser

### Production Deployment Options

#### Option 1: Heroku
- Add `Procfile`: `web: python server.py`
- Set environment variable: `heroku config:set MISTRAL_API_KEY=your-key`

#### Option 2: Vercel (Serverless)
- Deploy backend as serverless function
- Set environment variables in Vercel dashboard

#### Option 3: Railway/Render
- Connect GitHub repository
- Set environment variable in dashboard
- Auto-deploy on push

## Security Notes

- ✅ API key stored server-side only
- ✅ Never committed to Git (in `.env`, which is `.gitignore`d)
- ✅ Users cannot access the key
- ✅ All requests proxied through your server
