import os
import re
import json
import discord
from dotenv import load_dotenv
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound, PermissionDenied

# Load .env for local dev
load_dotenv(".env.local")

PROJECT_SECRET_ID = os.getenv("GOOGLE_CLOUD_PROJECT_SECRET_ID", "war-bot")

def decode_and_normalise_secret(raw: bytes) -> str:
    """
    Try UTF-8 first, then UTF-16-LE with BOM, then fall back to 'latin-1'.
    Strip BOM, nulls, and whitespace/newlines that often sneak in from Windows.
    """
    text = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16") 
        except UnicodeDecodeError:
            text = raw.decode("latin-1")  # last resort so we can clean it

    # Remove BOM if present and any NULs from UTF-16 artifacting
    text = text.replace("\ufeff", "").replace("\x00", "")
    # Trim CRLF/newlines/spaces/tabs
    text = text.strip()

    return text

def get_secret(secret_id: str, version_id: str = "latest") -> str:
    """Fetches a secret string from Google Secret Manager and normalises it."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_SECRET_ID}/secrets/{secret_id}/versions/{version_id}"
    try:
        resp = client.access_secret_version(request={"name": name})
        secret_text = decode_and_normalise_secret(resp.payload.data)

        # sanity check: Discord bot tokens are three dot-separated parts.
        if secret_id.startswith("discord_"):
            if secret_text.count(".") != 2:
                raise RuntimeError(
                    f"Secret '{secret_id}' does not look like a Discord bot token "
                    "(expected three dot-separated parts). Check you copied the Bot token from the "
                    "Developer Portal > Bot > Reset Token."
                )
        return secret_text
    except PermissionDenied:
        raise RuntimeError(f"No access to secret '{secret_id}'. Check IAM permissions.")
    except NotFound:
        raise RuntimeError(f"Secret or version not found: {name}")

# Select environment (local or prod)
env = os.getenv("PROJECT_ENVIRONMENT", "local")
print("Environment:", env)

# Fetch the Discord bot token
token = get_secret("discord_key_local" if env == "local" else "discord_key_prod")

# --- Discord Bot Setup ---
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# Ensure GUILD_ID is an int
GUILD_ID_ENV = os.getenv("GUILD_ID")
GUILD_ID = discord.Object(id=int(GUILD_ID_ENV) if GUILD_ID_ENV else 1436538029316636705)

@tree.command(name="hello", description="Say hello to the bot!", guild=GUILD_ID)
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello, {interaction.user.display_name}! 👋")

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    await tree.sync(guild=GUILD_ID)  # instant in this guild
    print(f"Slash commands synced to guild {GUILD_ID.id}")

    rt_war_channel_id = int(os.getenv("RT_WAR_ID"))
    ct_war_channel_id = int(os.getenv("CT_WAR_ID"))

    rt_channel = bot.get_channel(rt_war_channel_id)
    ct_channel = bot.get_channel(ct_war_channel_id)

    async def clear_and_post(channel: discord.TextChannel, placeholder: str):
        """Helper function to clear and then post in a channel."""
        try:
            deleted = await channel.purge()
            print(f"🧹 Cleared {len(deleted)} messages in {channel.name}")
        except discord.Forbidden:
            print(f"⚠️ No permission to delete messages in {channel.name}")
        except discord.HTTPException as e:
            print(f"⚠️ Error clearing {channel.name}: {e}")

        # Send the placeholder message
        await channel.send(placeholder)
        print(f"Sent placeholder in {channel.name}")

    if rt_channel:
        await clear_and_post(rt_channel, "Placeholder for RT War")
    else:
        print("RT war channel not found — check the ID or bot permissions.")

    if ct_channel:
        await clear_and_post(ct_channel, "Placeholder for CT War")
    else:
        print("CT war channel not found — check the ID or bot permissions.")

bot.run(token)
