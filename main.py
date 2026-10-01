import asyncio
import os
import logging
from dotenv import load_dotenv
from bot_interface import dp, bot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Load environment variables
    load_dotenv()
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    allowed_id = os.getenv("ALLOWED_TELEGRAM_USER_ID")
    
    if not token or not allowed_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or ALLOWED_TELEGRAM_USER_ID in environment variables.")
        return
        
    logger.info("Starting Jarvis Middleware...")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
