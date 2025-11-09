import os
from dotenv import load_dotenv
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound, PermissionDenied

load_dotenv(".env.local")  # dev convenience

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "war-bot")

def get_secret(secret_id: str, version_id: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    try:
        resp = client.access_secret_version(request={"name": name})
        return resp.payload.data.decode("utf-8")
    except PermissionDenied:
        raise RuntimeError(f"No access to secret '{secret_id}'. Check IAM for the service account.")
    except NotFound:
        raise RuntimeError(f"Secret or version not found: {name}")

env = os.getenv("PROJECT_ENVIRONMENT", "local")
print("Environment:", env)

secret = get_secret("discord_key_local" if env == "local" else "discord_key_prod")
print(secret)