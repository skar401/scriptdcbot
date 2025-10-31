import os
import time
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# ==============================
#        CONFIG & SETUP
# ==============================

load_dotenv()
BOT_TOKEN = os.getenv("MTQzMzkwNzI5NjQ4ODAwMTU1Ng.G3v3G0.h0zqZSSqXV8soJltKDw_Fy_emPSY3tFGG0u5nw")  # Stored securely in .env
ALLOWED_CHANNEL_NAME = "scriptos"
COOLDOWN_SECONDS = 60  # 1 minute

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

cooldowns = {}  # {user_id: timestamp}


# ==============================
#       KEEP-ALIVE SERVER
# ==============================

app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_web).start()


# ==============================
#          BOT EVENTS
# ==============================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


# ==============================
#      HASTEBIN UPLOAD
# ==============================

async def upload_to_hastebin(name: str, script_text: str, key: str) -> str:
    """Upload script to Hastebin and return the URL."""
    content = f"Name: {name}\n\nScript:\n{script_text}\n\nKey:\n{key}"
    async with aiohttp.ClientSession() as session:
        async with session.post("https://hastebin.com/documents", data=content.encode("utf-8")) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            key_id = data.get("key")
            return f"https://hastebin.com/{key_id}" if key_id else None


# ==============================
#        /script COMMAND
# ==============================

@bot.tree.command(name="script", description="Upload a script with name and key.")
@app_commands.describe(
    name="Name or title of the script.",
    script="The script text or code.",
    key="The key associated with the script."
)
async def script(interaction: discord.Interaction, name: str, script: str, key: str):
    # Only allowed channel
    if interaction.channel.name != ALLOWED_CHANNEL_NAME:
        await interaction.response.send_message(
            "⚠️ You can only use this command in **#scriptos**.",
            ephemeral=True
        )
        return

    # Cooldown check
    user_id = interaction.user.id
    now = time.time()
    if user_id in cooldowns:
        elapsed = now - cooldowns[user_id]
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            await interaction.response.send_message(
                f"⏳ Please wait **{remaining}** seconds before using `/script` again.",
                ephemeral=True
            )
            return
    cooldowns[user_id] = now

    # Defer response
    await interaction.response.defer(thinking=True)

    # Upload
    paste_url = await upload_to_hastebin(name, script, key)
    if not paste_url:
        await interaction.followup.send("❌ Failed to upload script. Try again later.")
        cooldowns.pop(user_id, None)
        return

    # Embed
    embed = discord.Embed(
        title=f"📜 {name}",
        description="Your script has been uploaded!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Script Preview", value=f"```{script[:100]}...```", inline=False)
    embed.add_field(name="Key", value=f"```{key}```", inline=False)
    embed.set_footer(text="Click the button below to view or copy the full script.")

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="🔗 View / Copy Script", style=discord.ButtonStyle.link, url=paste_url))

    await interaction.followup.send(embed=embed, view=view)


# ==============================
#   DELETE NON-COMMAND MESSAGES
# ==============================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.name == ALLOWED_CHANNEL_NAME:
        if not (message.content.startswith("/") or message.content.startswith("!")):
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, only `/script` commands are allowed here.",
                    delete_after=5
                )
            except discord.Forbidden:
                print("⚠️ Missing permission to delete messages.")
            except Exception as e:
                print(f"Error deleting message: {e}")
    await bot.process_commands(message)


# ==============================
#         RUN BOT
# ==============================

keep_alive()  # Keeps the bot alive on Replit
bot.run(BOT_TOKEN)
