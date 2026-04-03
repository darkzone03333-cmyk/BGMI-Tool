import os
import logging
import base64
import httpx
from io import BytesIO

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

from prompt import SYSTEM_PROMPT

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'google/gemini-flash-1.5')

if not TELEGRAM_BOT_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("Missing required environment variables: TELEGRAM_BOT_TOKEN and OPENROUTER_API_KEY")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message explaining how to use the bot."""
    welcome_message = """🎮 **Welcome to Galaxy Accounts Bot**

I analyze BGMI (Battlegrounds Mobile India) account screenshots and create formatted listings automatically.

**How to use:**
1️⃣ Send me a screenshot of a BGMI account
2️⃣ I'll extract the stats using AI
3️⃣ You'll get a formatted listing ready to share

**Supported stats:**
• UID, Level, Tier & Rank Points
• K/D Ratio, Matches, Win Rate
• Inventory items (skins, outfits, vehicles)

Just send a screenshot and I'll do the rest! 📸"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"User {update.effective_user.id} started the bot")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download photo, convert to base64, send to OpenRouter Vision API, reply with listing."""
    try:
        # Notify user that we're processing
        processing_msg = await update.message.reply_text("🔄 Analyzing screenshot...")
        
        # Get the largest photo
        photo_file = await update.message.photo[-1].get_file()
        
        # Download photo to bytes
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert to base64
        base64_image = base64.standard_b64encode(bytes(photo_bytes)).decode('utf-8')
        
        logger.info(f"Downloaded photo from user {update.effective_user.id}, size: {len(photo_bytes)} bytes")
        
        # Call OpenRouter Vision API
        listing = await get_listing_from_openrouter(base64_image)
        
        # Delete processing message
        try:
            await processing_msg.delete()
        except TelegramError:
            pass
        
        # Reply with the listing
        await update.message.reply_text(listing, parse_mode='HTML')
        logger.info(f"Sent listing to user {update.effective_user.id}")
        
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter API error for user {update.effective_user.id}: {e.response.status_code} - {e.response.text}")
        await handle_error(update, "API Error", "❌ OpenRouter API returned an error. Please try again later.")
        
    except Exception as e:
        logger.error(f"Error processing photo for user {update.effective_user.id}: {str(e)}")
        await handle_error(update, "Processing Error", f"❌ An error occurred while analyzing the screenshot: {str(e)[:100]}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages - ask user to send a screenshot instead."""
    response = "📸 Please send a BGMI account screenshot instead of text. I'll analyze it and create a formatted listing for you!"
    await update.message.reply_text(response)
    logger.info(f"User {update.effective_user.id} sent text message")


async def get_listing_from_openrouter(base64_image: str) -> str:
    """Send image to OpenRouter Vision API and get formatted listing."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/GalaxyAccountsBot",
        "X-Title": "BGMI Account Analyzer",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        listing = data['choices'][0]['message']['content'].strip()
        logger.info(f"Received response from OpenRouter: {len(listing)} characters")
        return listing


async def handle_error(update: Update, error_type: str, message: str) -> None:
    """Handle and send error messages to user."""
    try:
        await update.message.reply_text(message)
    except TelegramError as e:
        logger.error(f"Failed to send error message to user {update.effective_user.id}: {str(e)}")


def main() -> None:
    """Start the bot."""
    logger.info(f"Starting BGMI Account Analyzer bot with model: {OPENROUTER_MODEL}")
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Start the bot
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
