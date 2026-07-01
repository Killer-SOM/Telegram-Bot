import logging, httpx, os
from dotenv import load_dotenv
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
print("All env vars dotenv could see:")
print(os.getenv("TELEGRAM_BOT_TOKEN"))

log_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s| %(message)s",
     datefmt="%Y-%m-%d %H-%M-%S"
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

log_path = Path(__file__).parent / "bot.log"
file_handler = logging.FileHandler(log_path, encoding="utf-8")
file_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)
# logger.info(f"Logging initialised. Log file at: {log_path}")
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
conversation_history = {}
MAX_HISTORY_MESSAGES = 20

async def call_groq(messages: list) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers = {
                "Authorization" : f"Bearer {GROQ_API_KEY}",
                "Content-Type" : "application/json",
            },
            json = {
                "model" : GROQ_MODEL,
                "messages" : messages,
                "max_tokens": 500,
            },
            timeout = 30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[{chat_id}] /start command received.")
    await update.message.reply_text("Hey, I am an AI-Powered Bot.\nUse /reset to start a new conversation.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[{chat_id}] /help command received.")
    await update.message.reply_text(
        "Just type a message\n" 
        "My Commands are -\n /start and /help and /reset"
    )

async def reset(update: Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[{chat_id}] /reset command received. Cleared The Conversation.")
    conversation_history[chat_id] = []
    await update.message.reply_text("Conversation History Cleared!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"[{chat_id}] /stats command received.")
    
    if chat_id not in conversation_history or len(conversation_history[chat_id]) == 0:
        await update.message.reply_text("No conversation history yet.")
        return
    
    messages = conversation_history[chat_id]
    total_messages = len(messages)
    total_chars = sum(len(msg["content"]) for msg in messages)
    total_kb = total_chars / 1024

    user_messages = len([m for m in messages if m["role"] == "user"])
    bot_messages = len([m for m in messages if m["role"] == "assistant"])

    stats_text = (
        f"📊 **Conversation Stats**\n\n"
        f"Total messages: {total_messages}\n"
        f"User messages: {user_messages}\n"
        f"Bot replies: {bot_messages}\n"
        f"History size: {total_kb:.2f} KB"
    )

    await update.message.reply_text(stats_text, parse_mode = "Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    if chat_id not in conversation_history:
        conversation_history[chat_id] = []

    conversation_history[chat_id].append({"role" : "user", "content": user_text})

    conversation_history[chat_id] = conversation_history[chat_id][-MAX_HISTORY_MESSAGES:]

    await context.bot.send_chat_action(chat_id = chat_id, action = "typing")

    try:
        reply_text = await call_groq(conversation_history[chat_id])
    except Exception as e:
        logging.error(f"Error calling Groq API : {e}")
        await update.message.reply_text("Sorry, Something went wrong...\nTry Again.")
        return
    
    conversation_history[chat_id].append({"role" : "assistant", "content": reply_text})
    await update.message.reply_text(reply_text)

# async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_text = update.message.text
#     await update.message.reply_text(f"You Said: {user_text}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
