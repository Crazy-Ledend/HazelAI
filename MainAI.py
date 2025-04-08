import discord
import asyncio
import sqlite3
from discord.ext import commands
import google.generativeai as genai
import os
import re
import time
from dotenv import load_dotenv

# Token and API Key
load_dotenv()

TOKEN = os.getenv("TOKEN")
GOOGLE_API = os.getenv("GOOGLE_API")


def clean_response(text):
    # Define patterns that match polite or generic closing phrases
    patterns = [
        r"\s*How can I (help|assist|support) you( today)?\??$",
        r"\s*Let me know if (you need anything else|you have more questions)\.?$",
        r"\s*I'm here if you need (anything else|further assistance)\.?$",
        r"\s*Is there anything else I can (help|assist) with\??$",
        r"\s*Feel free to ask if you have more questions\.?$",
        r"\s*Do you need help with anything else\??$"
    ]

    for pattern in patterns:
        text = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE)

    return text.strip()


# --- Default Prompt ---
system_prompt = (
    "You're a chill, casual assistant. Talk like an average person, be friendly but keep replies short and clear (1–2 lines only unless really needed)."
    "\nKeep it real and avoid sounding like a robot or giving lectures.")

# --- Setup Gemini ---
GEN_API_KEY = GOOGLE_API
genai.configure(api_key=GEN_API_KEY)

# --- Discord Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- SQLite Setup ---
conn = sqlite3.connect("chat_memory.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    user_id TEXT,
    role TEXT,
    content TEXT
)
""")
conn.commit()


# --- Helper functions ---
def get_chat(user_id):
    cursor.execute("SELECT role, content FROM history WHERE user_id = ?",
                   (str(user_id), ))
    rows = cursor.fetchall()
    # convert to Gemini format
    return [{"role": role, "parts": [content]} for role, content in rows][-10:]


def save_chat(user_id, role, content):
    cursor.execute(
        "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
        (str(user_id), role, content))
    conn.commit()


# --- Bot Events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        async with message.channel.typing():
            await asyncio.sleep(0.3)

            try:
                model = genai.GenerativeModel("models/gemini-2.0-flash")

                # Remove mention and clean message
                clean_input = message.content.replace(f"<@{bot.user.id}>",
                                                      "").strip()

                # Get memory from DB
                chat_history = get_chat(message.author.id)

                # Start a new chat session with system prompt + memory
                chat = model.start_chat(history=[{
                    "role": "user",
                    "parts": [system_prompt]
                }, *chat_history])

                # Send the new user message
                response = chat.send_message(clean_input)

                # Clean and shorten response
                def trim_response(text, max_lines=3):
                    lines = text.strip().split("\n")
                    return "\n".join(lines[:max_lines])

                cleaned = clean_response(response.text)

                # Save both question and answer
                save_chat(message.author.id, "user", clean_input)
                save_chat(message.author.id, "model", cleaned)

                await message.channel.send(cleaned)

            except Exception as e:
                print(f"❌ Error: {e}")
                await message.channel.send(
                    ":warning: Oops! Something went wrong while talking to Gemini."
                )

    await bot.process_commands(message)


bot.run(TOKEN)
