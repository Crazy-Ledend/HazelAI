import discord
import asyncio
import sqlite3
from discord.ext import commands
import google.generativeai as genai
import os
import re
import json
import aiohttp
import importlib
from dotenv import load_dotenv
from urllib.parse import urlparse
from html import unescape
from serpapi import GoogleSearch
import random

# Load Tokens
load_dotenv()
TOKEN = os.getenv("TOKEN")
GOOGLE_API = os.getenv("GOOGLE_API")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
POKEMON_TYPES = "pokemon_types.json"

SEARCH_FOOTERS = [
    "🔍 Brought to you by Muffins 🍰",
	"📡 Muffins just Googled that for you",
	"Powered by Muffins • HazelTech 🦕",
	"Muffins did the Googling so you don’t have to 😤"
]
type_emojis = {
    "normal": "<:normal:1360320239581135212>",
    "fighting": "<:fighting:1360320252470235378>",
    "flying": "<:flying:1360320265778626651>",
    "poison": "<:poison:1360320197692756187>",
    "ground": "<:ground:1360320403880542309>",
    "rock": "<:rock:1360320383936368720>",
    "bug": "<:bug:1360320284971897053>",
    "ghost": "<:ghost:1360320300742479913>",
    "steel": "<:steel:1360320367834435694>",
    "fire": "<:fire:1360320496834580651>",
    "water": "<:water:1360320478207545476>",
    "grass": "<:grass:1360320450915471570>",
    "electric": "<:electric:1360320422704316759>",
    "psychic": "<:psychic:1360320314822623424>",
    "ice": "<:ice:1360320226314551568>",
    "dragon": "<:dragon:1360320213727576145>",
    "dark": "<:dark:1360320349115514974>",
    "fairy": "<:fairy:1360320327686684692>"
}

# Helper functions
def load_json(filename):
    """Load JSON safely."""
    if not os.path.exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

# Clean endings
def clean_response(text):
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


# Prompt
system_prompt = (
    "You're a chill, casual assistant. Talk like an average person, be friendly but keep replies short and clear (1–2 lines only unless really needed)."
    "\nKeep it real and avoid sounding like a robot or giving lectures."
    "\nPersonal Information: You are Muffins, developed by the HazelTech 🦕 Team, with crazypokeking as the CEO and founder, currently no other developers are working on HazelTech besides crazy pokeking (so he is your owner) (you don't hav to share your personal information unless asked)"
)

# Setup Gemini
genai.configure(api_key=GOOGLE_API)

# Setup Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="-", intents=intents)

# Setup SQLite
conn = sqlite3.connect("chat_memory.db")
cursor = conn.cursor()

# Global vars
bot.conn = conn
bot.cursor = cursor

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    user_id TEXT,
    role TEXT,
    content TEXT
)
""")
conn.commit()
cursor.execute("""
CREATE TABLE IF NOT EXISTS memory (
    user_id TEXT PRIMARY KEY,
    memory_data TEXT,
    times_updated INTEGER
)
""")
conn.commit()


def get_chat(user_id):
    cursor.execute("SELECT role, content FROM history WHERE user_id = ?",
                   (str(user_id), ))
    rows = cursor.fetchall()
    return [{"role": role, "parts": [content]} for role, content in rows][-20:]

def get_all():
    cursor.execute("SELECT role, content FROM history")
    rows = cursor.fetchall()
    return [{"role": role, "parts": [content]} for role, content in rows][-20:]

def save_chat(user_id, role, content):
    cursor.execute(
        "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
        (str(user_id), role, content))
    conn.commit()

def load_user_memory(user_id):
    cursor.execute("SELECT memory_data FROM memory WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return json.loads(row[0])
    return {}


def update_user_memory(user_id, model):
    cursor.execute("SELECT rowid, role, content FROM history WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    cursor.execute("SELECT times_updated FROM memory WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    count = result[0] if result else 0
    if len(rows) >= ((count+1)*10):
        # Grab the first 10 rows for summarization
        rows_to_summarize = rows[(-10):]
        history_prompt = "\n".join([f"{r[1]}: {r[2]}" for r in rows_to_summarize])
        summarization_prompt = history_prompt + "\n\nSummarize the user profile from this conversation into key facts in JSON format (e.g., nickname, preferences, interests, personality traits, etc.)."

        # Call Gemini or ChatGPT model
        chat = model.start_chat(history=[])
        response = chat.send_message(summarization_prompt)

        try:
            memory_data = json.loads(response.text)  # Expecting JSON format
        except json.JSONDecodeError:
            memory_data = {"note": "Could not parse memory"}  # Fallback
            
        # Save/update memory
        cursor.execute("REPLACE INTO memory (user_id, memory_data, times_updated) VALUES (?, ?, ?)", (user_id, json.dumps(memory_data), count+1))

        conn.commit()

# --- Pokepaste handlers ---


def strip_html_tags(text):
    return re.sub(r"<[^>]+>", "", unescape(text))


async def fetch_pokepaste_content(message_text):
    match = re.search(r"https?://pokepast\.es/([a-zA-Z0-9]+)", message_text)
    if not match:
        raise ValueError("No valid Pokepaste URL found.")

    paste_id = match.group(1)
    raw_url = f"https://pokepast.es/raw/{paste_id}"
    html_url = f"https://pokepast.es/{paste_id}"

    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession(headers=headers) as session:
        # Try raw first
        async with session.get(raw_url) as raw_resp:
            if raw_resp.status == 200:
                return await raw_resp.text()

        # Fallback to HTML <pre> block (with aggressive HTML stripping)
        async with session.get(html_url) as html_resp:
            if html_resp.status != 200:
                raise ValueError(
                    f"Failed to fetch Pokepaste page (status: {html_resp.status})"
                )

            html = await html_resp.text()

            # Find all <pre> blocks (just in case there are multiple)
            matches = re.findall(r"<pre.*?>(.*?)</pre>", html, re.DOTALL)
            if not matches:
                raise ValueError("Could not extract <pre> content.")

            # Join all blocks, strip tags and unescape
            raw_blocks = []
            for m in matches:
                cleaned = re.sub(r"<[^>]+>", "", m)
                raw_blocks.append(unescape(cleaned.strip()))

            return "\n\n".join(raw_blocks)


def parse_pokepaste(paste):
    sets = []
    blocks = re.split(r"\n\s*\n", paste.strip())  # Split sets by empty lines

    for block in blocks:
        lines = block.strip().splitlines()

        for line in lines:
            line = line.strip()  # ✅ sanitize line!

        current = {"moves": []}
        for line in lines:
            if "@" in line:
                parts = line.split(" @ ")
                current["name"] = parts[0].strip()
                current["item"] = parts[1].strip() if len(parts) > 1 else ""
            elif line.startswith("Ability:"):
                current["ability"] = line.split(":", 1)[1].strip()
            elif line.startswith("Tera Type:"):
                current["tera"] = line.split(":", 1)[1].strip()
            elif line.startswith("EVs:"):
                current["evs"] = line.split(":", 1)[1].strip()
            elif line.strip().endswith("Nature"):
                current["nature"] = line.strip()
            elif line.startswith("- "):
                current["moves"].append(line[2:].strip())
        if current.get("name"):
            sets.append(current)

    return sets


def summarize_sets(sets):
    summaries = []
    for s in sets:
        name = s.get("name", "Unknown Pokémon")
        item = s.get("item", "No item")
        moves = ", ".join(s.get("moves", []))
        summaries.append(f"> **{name}** (@{item}) → {moves}")

    summaries = [re.sub(r"[^\x00-\x7F]+", "", s) for s in summaries]
    return summaries


def create_embeds(sets):
    embeds = []
    pokemon_types = load_json(POKEMON_TYPES)
    for s in sets:
        title = s.get("name", "Pokémon")

        # Try to get proper key match for Pokémon name (case-insensitive fallback)
        poke_key = title.strip().split()[0].lower().capitalize()
        types = pokemon_types.get(poke_key, ["normal"])
        type_display = " ".join(f"{type_emojis.get(t.lower(), '')} `{t.capitalize()}`" for t in types)
        embed = discord.Embed(
            title=f"{title}",
            description=f"**Types:** {type_display}\n\n**Moves:**\n" +
                        "\n".join(f"<a:dot:1359934692467413103> {m}" for m in s.get("moves", [])),
            color=discord.Color.blurple()
        )

        if "evs" in s:
            embed.add_field(name="EVs", value=s["evs"], inline=False)
        if "nature" in s:
            embed.add_field(name="Nature", value=s["nature"], inline=False)
        if "item" in s:
            embed.add_field(name="Item", value=s["item"], inline=True)
        if "ability" in s:
            embed.add_field(name="Ability", value=s["ability"], inline=True)
        if "tera" in s:
            embed.add_field(name="Tera Type", value=s["tera"], inline=True)

        embeds.append(embed)
    return embeds

def search_summary(query, api_key):
    try:
        search = GoogleSearch({
            "q": query,
            "api_key": api_key
        })
        results = search.get_dict()

        if "organic_results" in results and len(results["organic_results"]) > 0:
            first_result = results["organic_results"][0]
            title = first_result.get("title", "No title")
            snippet = first_result.get("snippet", "No description available.")
            link = first_result.get("link", "")

            return {
                "title": title,
                "description": snippet,
                "url": link
            }
        else:
            return {
                "title": "No Results Found",
                "description": "Could not find anything relevant.",
                "url": ""
            }

    except Exception as e:
        print(f"❌ Search Error: {e}")
        return {
            "title": "Error",
            "description": "Something went wrong while searching.",
            "url": ""
        }

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await setup_extensions()
    await bot.tree.sync()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        async with message.channel.typing():
            await asyncio.sleep(0.3)
            try:
                content = message.content.replace(f"<@{bot.user.id}>",
                                                  "").strip()

                # Model selection
                model = genai.GenerativeModel("models/gemini-2.0-flash")
                
                if content.lower().startswith("search:"):
                    query = content[len("search:"):].strip()
                    api_key = os.getenv("SERPAPI_KEY")
                    if not api_key:
                        await message.channel.send("❌ SERPAPI key not found in environment.")
                        return

                    result = search_summary(query, api_key)
                    embed = discord.Embed(
                        title=result["title"],
                        description=result["description"],
                        url=result["url"],
                        color=discord.Color.green()
                    )
                    embed.set_footer(text=random.choice(SEARCH_FOOTERS))

                    await message.channel.send(embed=embed)

                # Check for Pokepaste link
                if "pokepast.es" in content:
                    try:
                        paste = await fetch_pokepaste_content(content)
                        sets = parse_pokepaste(paste)

                        if any(word in content.lower()
                               for word in ["summary", "summarize", "list"]):
                            summary = summarize_sets(sets)

                            chat = model.start_chat(
                                history=[{
                                    "role": "user",
                                    "parts": [system_prompt]
                                }])
                            prompt = f"""{summary}
                                Now write a detailed analysis of this Pokémon team in about 400–500 words. 
                                Discuss synergy, threats, potential roles, and overall effectiveness in competitive play."""
                            
                            response = chat.send_message(prompt)
                            cleaned = clean_response(response.text)

                            save_chat(message.author.id, "user", content)
                            save_chat(message.author.id, "model", cleaned)

                            await message.channel.send("\n\n".join(summary))
                            await message.channel.send(f"\n{cleaned}")
                            return

                        if any(word in content.lower()
                               for word in ["display", "embed", "show"]):
                            embeds = create_embeds(sets)
                            for embed in embeds:
                                await message.channel.send(embed=embed)
                            return

                        await message.channel.send(
                            "Found a Pokepaste! Use `summary` or `display` in your message to get more details."
                        )
                        return

                    except Exception as e:
                        print(f"❌ Error in Pokepaste handler: {e}")
                        await message.channel.send(
                            "❌ Couldn't fetch or process the Pokepaste link.")
                        return
                    
  
                # Fallback to Gemini chat
                history = get_chat(message.author.id)[-40:]
                
                memory_data = load_user_memory(message.author.id)
                if memory_data:
                    memory_text = json.dumps(memory_data, indent=2)
                    history.append({"role": "user", "parts": [f"User profile:\n{memory_text}"]})
                    

                chat = model.start_chat(history=[{
                    "role": "user",
                    "parts": [system_prompt]
                }, *history])
                response = chat.send_message(content)
                cleaned = clean_response(response.text)

                save_chat(message.author.id, "user", content)
                save_chat(message.author.id, "model", cleaned)
                update_user_memory(message.author.id, model)

                await message.channel.send(cleaned)

            except Exception as e:
                print(f"❌ Error: {e}")
                await message.channel.send(
                    ":warning: Oops! Something went wrong while talking to Muffins."
                )

    await bot.process_commands(message)
    
# Reload command
@bot.hybrid_command(name="reload", description="Reload Modules (Owner only)")
@commands.is_owner()  # Restrict this command to the bot owner
async def reload(ctx, module_name: str = None):
    if module_name == None:
        await ctx.send("<:discord_cross:1321809722151534645> | `Invalid syntax`")
        return
    try:
        # Unload if the module was previously loaded as an extension
        await bot.unload_extension(module_name)
    except commands.ExtensionNotLoaded:
        pass  # Ignore if it wasn't already loaded

    try:
        # Reload the module using importlib
        module = importlib.import_module(module_name)
        importlib.reload(module)

        # Load the extension back
        await bot.load_extension(module_name)
        await ctx.send(f"✅ `{module_name}` reloaded successfully!")
    except ModuleNotFoundError:
        await ctx.send(f"❌ `{module_name}` not found. Make sure it's importable and named correctly.")
    except Exception as e:
        await ctx.send(f"❌ Failed to reload `{module_name}`: `{e}`") 
    
async def setup_extensions():
    await bot.load_extension("info")
    await bot.load_extension("logs")
    await bot.load_extension("presence")

bot.run(TOKEN)
