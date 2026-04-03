import os
import logging
import base64
import asyncio
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


# Global dict to store pending media groups during batching
# Format: {media_group_id: {'chat_id': int, 'photos': [file_id, ...], 'task': asyncio.Task}}
pending_media_groups = {}


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
    """Handle photo messages - check for media group and batch if needed."""
    media_group_id = update.message.media_group_id
    
    if media_group_id:
        # This photo is part of a media group (multiple photos sent at once)
        chat_id = update.effective_chat.id
        photo_file_id = update.message.photo[-1].file_id
        
        if media_group_id not in pending_media_groups:
            # First photo in this group - initialize and schedule processing
            pending_media_groups[media_group_id] = {
                'chat_id': chat_id,
                'photos': [photo_file_id],
                'task': None
            }
            # Schedule processing after 1.5 second buffer (wait for other photos to arrive)
            task = asyncio.create_task(process_media_group(media_group_id, context))
            pending_media_groups[media_group_id]['task'] = task
            logger.info(f"Started collecting media group {media_group_id}, got photo 1")
        else:
            # Add this photo to the existing group
            pending_media_groups[media_group_id]['photos'].append(photo_file_id)
            logger.info(f"Added photo to media group {media_group_id}, total photos: {len(pending_media_groups[media_group_id]['photos'])}")
    else:
        # Single photo (no media group) - process immediately
        await process_single_photo(update, context)


async def process_media_group(media_group_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process all photos in a media group after waiting for collection."""
    # Wait 1.5 seconds to collect all photos in the group
    await asyncio.sleep(1.5)
    
    if media_group_id not in pending_media_groups:
        logger.warning(f"Media group {media_group_id} not found in pending groups")
        return
    
    group_data = pending_media_groups.pop(media_group_id)
    chat_id = group_data['chat_id']
    photos = group_data['photos']
    
    try:
        # Send processing status message
        processing_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔄 Analyzing {len(photos)} screenshot{'s' if len(photos) > 1 else ''}..."
        )
        
        logger.info(f"Processing media group {media_group_id} with {len(photos)} photos")
        
        # Download and analyze each photo
        listings = []
        for i, file_id in enumerate(photos, 1):
            try:
                file_info = await context.bot.get_file(file_id)
                photo_bytes = await file_info.download_as_bytearray()
                base64_image = base64.standard_b64encode(bytes(photo_bytes)).decode('utf-8')
                
                # Send to OpenRouter Vision API
                listing = await get_listing_from_openrouter(base64_image)
                listings.append(listing)
                logger.info(f"Analyzed photo {i}/{len(photos)} from media group {media_group_id}")
                
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenRouter API error for photo {i} in media group {media_group_id}: {e.response.status_code}")
                listings.append(f"❌ **OpenRouter API Error** (Photo {i})\nPlease try again later.")
            except Exception as e:
                logger.error(f"Error analyzing photo {i} from media group {media_group_id}: {str(e)}")
                listings.append(f"❌ **Error analyzing photo {i}**\n{str(e)[:80]}")
        
        # Combine all listings into one message
        combined_message = ""
        for i, listing in enumerate(listings, 1):
            combined_message += f"━━━━━━━━━━━━━━━━━━━\n📸 ACCOUNT {i} of {len(listings)}\n━━━━━━━━━━━━━━━━━━━\n{listing}\n\n"
        
        # Delete the processing message
        try:
            await processing_msg.delete()
        except TelegramError:
            pass
        
        # Send the combined reply
        await context.bot.send_message(chat_id=chat_id, text=combined_message, parse_mode='HTML')
        logger.info(f"Sent combined reply for media group {media_group_id} with {len(photos)} account(s)")
        
    except Exception as e:
        logger.error(f"Unexpected error processing media group {media_group_id}: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=group_data['chat_id'],
                text=f"❌ **Unexpected Error**\n{str(e)[:100]}"
            )
        except TelegramError:
            logger.error(f"Failed to send error message for media group {media_group_id}")


async def process_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process a single photo (not part of a media group)."""
    try:
        # Notify user we're processing
        processing_msg = await update.message.reply_text("🔄 Analyzing screenshot...")
        
        # Download photo
        photo_file = await update.message.photo[-1].get_file()
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
        await handle_error(update, "API Error", "❌ **OpenRouter API Error**\nThe API returned an error. Please try again later.")
        
    except Exception as e:
        logger.error(f"Error processing photo for user {update.effective_user.id}: {str(e)}")
        await handle_error(update, "Processing Error", f"❌ **Error Processing Screenshot**\n{str(e)[:100]}")



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
