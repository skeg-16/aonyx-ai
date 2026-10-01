import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from dotenv import load_dotenv
import logging
from router import route_command
from executors.voice import transcribe_voice

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_TELEGRAM_USER_ID", 0))

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

logger = logging.getLogger(__name__)

# Security Middleware - Simple check for allowed user
@dp.message()
async def security_check_and_route(message: types.Message):
    if message.from_user.id != ALLOWED_USER_ID:
        logger.warning(f"Unauthorized access attempt from User ID: {message.from_user.id}")
        await message.answer("Access Denied.")
        return
        
    # Handle Voice Messages
    if message.voice:
        logger.info("Received voice message.")
        status_msg = await message.answer("🎙️ Listening...")
        
        # Download voice file
        file_id = message.voice.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        download_path = f"voice_{file_id}.ogg"
        await bot.download_file(file_path, download_path)
        
        # Transcribe
        try:
            transcript = await transcribe_voice(download_path)
            await status_msg.edit_text(f"🗣️ You said: _{transcript}_", parse_mode="Markdown")
            
            # Route transcribed text
            if transcript.strip():
                await route_command(transcript, message, bot)
                
        except Exception as e:
            logger.error(f"Voice processing error: {e}")
            await status_msg.edit_text("❌ Error processing voice command.")
        finally:
            if os.path.exists(download_path):
                os.remove(download_path)
        return

    # Handle Text Messages
    if message.text:
        await route_command(message.text, message, bot)
