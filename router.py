import logging
from aiogram import types, Bot
from executors.ollama import generate_response
from executors.antigravity import execute_antigravity_task

logger = logging.getLogger(__name__)

async def route_command(text: str, message: types.Message, bot: Bot):
    text = text.strip()
    
    if not text:
        return

    # Check for Antigravity Commands
    if text.lower().startswith(("/jarvis", "/task", "/code")):
        # Extract the actual task
        task_prompt = text.split(" ", 1)[1] if " " in text else ""
        if not task_prompt:
            await message.answer("Please provide a task for Antigravity.")
            return
            
        status_msg = await message.answer("🚀 Dispatching task to Antigravity...")
        # Invoke Antigravity CLI asynchronously
        result = await execute_antigravity_task(task_prompt)
        
        # Send result back (Handling long messages by chunking if necessary, but simple for now)
        if len(result) > 4000:
            result = result[:3900] + "\n...[Output Truncated]"
        await status_msg.edit_text(f"```text\n{result}\n```", parse_mode="MarkdownV2")
        return

    # Otherwise, route to local Ollama for conversation/questions
    try:
        status_msg = await message.answer("🤔 Thinking...")
        response = await generate_response(text)
        if len(response) > 4000:
            response = response[:3900] + "\n...[Output Truncated]"
        await status_msg.edit_text(response)
    except Exception as e:
        logger.error(f"Error in Ollama generation: {e}")
        await message.answer("❌ Failed to reach local LLM.")
