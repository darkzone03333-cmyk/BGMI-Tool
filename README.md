# BGMI Account Analyzer Bot

A Telegram bot that analyzes BGMI (Battlegrounds Mobile India) account screenshots using OpenRouter Vision API and generates formatted account listings automatically.

## Features

- ✅ Download BGMI account screenshots from Telegram
- ✅ Extract account stats using Google Gemini Flash Vision API
- ✅ Auto-format stats into professional listings
- ✅ Display inventory items (gun skins, outfits, vehicles)
- ✅ Async/polling-based (no webhook required)
- ✅ Fully configurable via environment variables
- ✅ Comprehensive error handling
- ✅ Production-ready logging

## Project Structure

```
bgmi-bot/
├── bot.py           # Main bot application
├── prompt.py        # AI system prompt for listing format
├── requirements.txt # Python dependencies
├── Procfile        # Railway deployment config
└── README.md       # This file
```

## File Descriptions

### bot.py
- Uses `python-telegram-bot==21.6` (async version with Application API)
- Handles `/start` command with welcome message
- Processes photo messages: downloads, converts to base64, queries OpenRouter API
- Handles text messages with instructions
- Async HTTP requests via `httpx`
- Comprehensive logging and error handling

### prompt.py
- Contains `SYSTEM_PROMPT` variable
- Instructs AI to analyze BGMI screenshots and extract stats
- Specifies exact listing format with emojis and structure
- Handles N/A values and missing inventory

### requirements.txt
- `python-telegram-bot==21.6` - Async Telegram bot library
- `httpx==0.27.2` - Async HTTP client

### Procfile
- `worker: python bot.py` - Railway worker process (no web server)

## Getting API Keys

### 1. Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send command `/newbot`
3. Follow prompts to name your bot and choose username
4. BotFather will provide your `TELEGRAM_BOT_TOKEN`
5. Save this token (keep it secret!)

### 2. OpenRouter API Key
1. Visit [openrouter.ai](https://openrouter.ai)
2. Sign up or log in
3. Go to the dashboard and find "API Key" section
4. Create/copy your `OPENROUTER_API_KEY`
5. Add credits to your account (free tier available)

## Environment Variables

Add these to your Railway project:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=google/gemini-flash-1.5  (optional, defaults to this)
```

## Deployment on Railway

### Step 1: Prepare Your Repository

1. Create a new GitHub repository (or use existing)
2. Clone it locally:
   ```bash
   git clone https://github.com/yourusername/bgmi-bot.git
   cd bgmi-bot
   ```

3. Copy all 5 files (`bot.py`, `prompt.py`, `requirements.txt`, `Procfile`, `README.md`) into the repository

4. Create a `.gitignore` file:
   ```
   __pycache__/
   *.pyc
   .env
   venv/
   ```

5. Commit and push:
   ```bash
   git add .
   git commit -m "Initial BGMI bot setup"
   git push origin main
   ```

### Step 2: Deploy on Railway

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click **New Project** → **Deploy from GitHub repo**
4. Select your `bgmi-bot` repository
5. Railway will auto-detect the service

### Step 3: Configure Environment Variables

1. In Railway project dashboard, go to **Variables**
2. Add these three environment variables:
   - `TELEGRAM_BOT_TOKEN` = your BotFather token
   - `OPENROUTER_API_KEY` = your OpenRouter API key
   - `OPENROUTER_MODEL` = `google/gemini-flash-1.5` (optional)

3. Click **Deploy** to trigger auto-deployment

### Step 4: Verify Deployment

1. In Railway dashboard, check the **Logs** tab
2. Should see: `"Starting BGMI Account Analyzer bot with model: google/gemini-flash-1.5"`
3. Open Telegram and search for your bot (by username from BotFather)
4. Send `/start` - bot should reply with welcome message
5. Send a BGMI screenshot - bot should analyze and reply with formatted listing

## Troubleshooting

### Bot not responding?
- Check Railway logs for errors
- Verify `TELEGRAM_BOT_TOKEN` is correct (no spaces)
- Ensure bot username matches BotFather username

### "OpenRouter API error"?
- Check `OPENROUTER_API_KEY` is valid
- Verify your OpenRouter account has credits
- Check API response in Railway logs

### Photo not downloading?
- Ensure bot has permissions to download files
- Try a different BGMI screenshot file
- Check internet connection on Railway

### Listing format looks wrong?
- Edit `SYSTEM_PROMPT` in `prompt.py`
- Commit and push changes
- Railway will auto-redeploy

## Free Vision Models on OpenRouter

These free/cheap models work well for screenshot analysis:

| Model | Provider | Cost | Notes |
|-------|----------|------|-------|
| `google/gemini-flash-1.5` | Google | $0.075/1M input | **Recommended** - Fast, accurate |
| `google/gemini-pro-vision` | Google | Free | Good alternative, might be slower |
| `openai/gpt-4-vision` | OpenAI | $0.01/image | Slower, higher quality |
| `anthropic/claude-3-haiku-vision` | Anthropic | $0.003/image | Budget option |

Set `OPENROUTER_MODEL` environment variable to use different model.

## Code Features Explained

### Async Architecture
- Uses `python-telegram-bot` Application API (fully async)
- `httpx.AsyncClient` for non-blocking API calls
- `run_polling(drop_pending_updates=True)` for clean restarts

### Error Handling
- Catches `httpx.HTTPStatusError` separately for API errors
- Catches general exceptions with user-friendly messages
- All errors logged with user ID and context

### Logging
- Python `logging` module configured
- Logs include timestamps, module name, and log level
- All actions logged: start, photo download, API calls, errors

### Security
- Never hardcodes API keys (uses environment variables)
- Validates required env vars on startup
- No user whitelist (open to all, can be restricted later)

## Customization

### Change Listing Format
Edit the format in `prompt.py` `SYSTEM_PROMPT` variable. The AI will follow the new format in its output.

### Add More Commands
Add handlers in `bot.py`:
```python
application.add_handler(CommandHandler("yourcommand", your_function))
```

### Change Vision Model
Set `OPENROUTER_MODEL` environment variable to a different model from OpenRouter's model list.

### Add Database
Currently stateless. To add persistent storage (PostgreSQL, MongoDB), add connection in Railway Variables and update `bot.py` imports.

## Python Version

Requires Python 3.11 or higher. Check your Railway Python version in project settings (usually 3.12 by default).

## License

MIT License - Feel free to fork and modify!

## Support

For issues with:
- **Telegram Bot API**: [python-telegram-bot docs](https://python-telegram-bot.readthedocs.io/)
- **OpenRouter API**: [openrouter.ai docs](https://openrouter.ai/docs)
- **Railway Deployment**: [railway.app docs](https://docs.railway.app/)
