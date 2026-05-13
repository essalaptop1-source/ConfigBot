import discord
from discord import app_commands
import os
from flask import Flask
from threading import Thread

# 1. Setup Flask Web Server to satisfy Render's health checks
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Configure Client (User-installed slash apps don't need server text intents)
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        print("Syncing global application commands...")
        await self.tree.sync()
        print("Commands synced successfully!")

client = MyClient()

# 3. Create Global Slash Command
@client.tree.command(
    name="flood",
    description="Delivers the configuration payload.",
    integration_types={discord.IntegrationType.user},  # 1 = Follows your user profile everywhere
    allowed_contexts={discord.InteractionContextType.guild}  # 0 = Usable inside server text channels
)
async def flood(interaction: discord.Interaction):
    # Initial mandatory response to anchor the stream
    await interaction.response.send_message("⚠️ **Initializing Payload Delivery...**")

    YOUR_DISCORD_LINK = "YOUR_DISCORD_SERVER_LINK_HERE"
    payload_text = (
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**"
    )

    try:
        # Pushes the multi-line payload block into the channel
        await interaction.followup.send(content=payload_text)
    except discord.errors.Forbidden:
        print("Dropped: Server administrator has blocked external application outputs.")
    except Exception as e:
        print(f"Failed to post: {e}")

if __name__ == "__main__":
    server_thread = Thread(target=run_web_server)
    server_thread.start()

    BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
    client.run(BOT_TOKEN)
