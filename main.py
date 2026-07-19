import os
from dotenv import load_dotenv
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound, PermissionDenied

import interactions  # interactions.py

from utils.config import DEV, GUILD_IDS, PROJECT_ENV, SCOPES

load_dotenv(".env.local")

PROJECT_SECRET_ID = os.getenv("GOOGLE_CLOUD_PROJECT_SECRET_ID", "war-bot")

print("Environment:", PROJECT_ENV)
print("DEV MODE:", DEV)


def _load_lounge_api_key() -> None:
    from utils.lounge_api import set_lounge_api_key

    # Prefer .env.local override for local testing; otherwise GCP Secret Manager.
    key = os.getenv("LOUNGE_API_KEY", "").strip()
    if not key:
        try:
            key = get_secret("lounge_api_key")
        except Exception as exc:
            print(f"⚠️ Lounge API key not loaded ({exc}).")
            return
    set_lounge_api_key(key)
    print("Lounge API key configured.")


# ---------------------------
# Secrets Helpers
# ---------------------------
def decode_and_normalise_secret(raw: bytes) -> str:
    """
    Try UTF-8 first, then UTF-16 (handles BOM), then 'latin-1'.
    Strip BOM, nulls, and trailing whitespace/newlines.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

    text = text.replace("\ufeff", "").replace("\x00", "")
    return text.strip()


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
                    "(expected three dot-separated parts)."
                )
        return secret_text
    except PermissionDenied:
        raise RuntimeError(f"No access to secret '{secret_id}'. Check IAM permissions.")
    except NotFound:
        raise RuntimeError(f"Secret or version not found: {name}")


# ---------------------------
# Fetch the Discord bot token
# ---------------------------
token = get_secret("discord_key_local" if DEV else "discord_key_prod")


# ---------------------------
# interactions.py Client
# ---------------------------
bot = interactions.Client(
    token=token,
    intents=interactions.Intents.DEFAULT | interactions.Intents.MESSAGE_CONTENT,
    send_command_tracebacks=False,
)


# ---------------------------
# Slash Commands
# ---------------------------
@interactions.slash_command(
    name="hello",
    description="Say hello to the bot!",
    scopes=SCOPES,
)
async def hello(ctx: interactions.SlashContext):
    await ctx.send(f"Hello, {ctx.author.display_name}! 👋", ephemeral=False)


# ---------------------------
# Ready Event
# ---------------------------
@interactions.listen()
async def on_startup():
    user = bot.user
    print(f"Logged in as {user.tag} ({user.id})")

    if DEV:
        print(f"⚡ DEV MODE: Slash commands registered instantly to guild(s) {GUILD_IDS}")
    else:
        print("🌍 PROD MODE: Slash commands registered globally (may take up to 1 hour)")

    rt_war_channel_id = int(os.getenv("RT_WAR_ID")) if os.getenv("RT_WAR_ID") else None
    ct_war_channel_id = int(os.getenv("CT_WAR_ID")) if os.getenv("CT_WAR_ID") else None

    async def clear_and_post(channel_id: int, placeholder: str):
        if not channel_id:
            print("Channel ID missing.")
            return

        try:
            channel = await bot.fetch_channel(channel_id)
            if channel is None:
                print(f"Channel {channel_id} not found — check permissions.")
                return
        except Exception as e:
            print(f"Error fetching channel {channel_id}: {e}")
            return

        cleared = 0
        try:
            recent = await channel.fetch_messages(limit=100)
            for msg in recent:
                try:
                    await msg.delete()
                    cleared += 1
                except interactions.errors.LibraryException:
                    pass
            print(f"Cleared {cleared} messages in #{channel.name}")
        except Exception as e:
            print(f"Error clearing #{channel.name}: {e}")

        try:
            await channel.send(placeholder)
            print(f"Sent placeholder in #{channel.name}")
        except Exception as e:
            print(f"Error sending to #{channel.name}: {e}")

    if rt_war_channel_id:
        await clear_and_post(rt_war_channel_id, "Placeholder for RT War")
    else:
        print("RT war channel not configured — set RT_WAR_ID in env.")

    if ct_war_channel_id:
        await clear_and_post(ct_war_channel_id, "Placeholder for CT War")
    else:
        print("CT war channel not configured — set CT_WAR_ID in env.")


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    _load_lounge_api_key()
    bot.load_extension("cogs.setup")
    bot.load_extension("cogs.team")
    bot.load_extension("cogs.profile")
    bot.load_extension("cogs.queue")
    bot.load_extension("cogs.war_commands")
    bot.load_extension("cogs.help")
    bot.load_extension("cogs.queue_interactions")
    bot.load_extension("cogs.war_view")
    bot.load_extension("cogs.war_interactions")
    bot.load_extension("cogs.match_interactions")
    bot.load_extension("cogs.match_relay")
    bot.load_extension("cogs.submit_pen")
    bot.load_extension("cogs.post_war_billboard")
    bot.start()
