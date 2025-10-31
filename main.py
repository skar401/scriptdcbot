import os
import time
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# =========================
#   CONFIGURATION
# =========================

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
PASTEBIN_API_KEY = os.getenv("PASTEBIN_API_KEY")

ALLOWED_CHANNEL_NAME = "scriptos"
COOLDOWN_SECONDS = 60  # 1 minute cooldown

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
cooldowns = {}  # {user_id: timestamp}

# =========================
#   KEEP-ALIVE WEB SERVER
# =========================
app = Flask('')

@app.route('/')
def home():
    return "✅ Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_web).start()

# =========================
#   BOT EVENTS
# =========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# =========================
#   PASTEBIN UPLOAD
# =========================
async def upload_to_pastebin(name: str, script_text: str, key: str) -> str:
    """Uploads the script to Pastebin and returns the paste URL."""
    if not PASTEBIN_API_KEY:
        print("❌ Missing Pastebin API key.")
        return None

    paste_content = f"Name: {name}\n\nScript:\n{script_text}\n\nKey:\n{key}"

    data = {
        "api_dev_key": PASTEBIN_API_KEY,
        "api_option": "paste",
        "api_paste_code": paste_content,
        "api_paste_name": name,
        "api_paste_private": "1",  # 0 = public, 1 = unlisted, 2 = private
        "api_paste_expire_date": "N",  # Never expires
        "api_paste_format": "text"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://pastebin.com/api/api_post.php", data=data) as resp:
            if resp.status != 200:
                print(f"❌ Pastebin upload failed with status {resp.status}")
                return None
            paste_url = await resp.text()
            if paste_url.startswith("http"):
                return paste_url
            else:
                print(f"❌ Pastebin error: {paste_url}")
                return None

# =========================
#   SLASH COMMAND: /script
# =========================
@bot.tree.command(name="script", description="Upload a script with name and key.")
@app_commands.describe(
    name="Name or title of the script.",
    script="The script text or code.",
    key="The key associated with the script."
)
async def script(interaction: discord.Interaction, name: str, script: str, key: str):
    if interaction.channel.name != ALLOWED_CHANNEL_NAME:
        await interaction.response.send_message(
            f"⚠️ Use this command only in **#{ALLOWED_CHANNEL_NAME}**.",
            ephemeral=True
        )
        return

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

    await interaction.response.defer(thinking=True)

    # Upload to Pastebin
    paste_url = await upload_to_pastebin(name, script, key)
    if not paste_url:
        await interaction.followup.send("❌ Failed to upload script. Try again later.")
        cooldowns.pop(user_id, None)
        return

    # Embed message
    embed = discord.Embed(
        title=f"📜 {name}",
        description="Your script has been uploaded to Pastebin!",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Script Preview", value=f"```{script[:100]}...```", inline=False)
    embed.add_field(name="Key", value=f"```{key}```", inline=False)
    embed.set_footer(text="Click below to view or copy the full script.")

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="🔗 View on Pastebin",
            style=discord.ButtonStyle.link,
            url=paste_url
        )
    )

    await interaction.followup.send(embed=embed, view=view)

# =========================
#   MESSAGE FILTER
# =========================
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

# =========================
#   RUN BOT
# =========================
keep_alive()
bot.run(BOT_TOKEN)
