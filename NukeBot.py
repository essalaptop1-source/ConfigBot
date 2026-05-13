import discord
from discord.ext import commands
import asyncio
import os
from flask import Flask
from threading import Thread

# 1. Setup Flask Web Server to satisfy Render's health checks
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Render assigns a dynamic port via environment variables
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Configure the Discord Bot Intents and Prefixes
intents = discord.Intents.default()
intents.message_content = True  # Required to read text prefix signals

bot = commands.Bot(command_prefix=("!", "$", ".", ","), intents=intents)
is_running = False

@bot.event
async def on_ready():
    print(f"Bot connected successfully as: {bot.user.name}")

# Command: Start streaming text blocks
@bot.command(name="start")
async def start_payload(ctx):
    global is_running
    
    if is_running:
        await ctx.send("⚠️ Streaming loop is already active!")
        return
        
    is_running = True
    await ctx.send("🚀 Starting transmission loop...")

    # YOUR SPECIFIC CUSTOM DISCORD PAYLOAD BLOCK
    # TODO: Replace the placeholder link below with your exact server invite link!
    YOUR_DISCORD_LINK = "discord.gg"
    
    payload_text = (
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**\n"
        f"# **POWER OF CONFIG2 https://discord.gg/dt248N6Be**"
    )

    while is_running:
        try:
            await ctx.send(payload_text)
            # 2.5 second sleep duration protects against an absolute gateway ban
            await asyncio.sleep(2.5) 
        except discord.errors.Forbidden:
            print("Lacking text permissions in this channel.")
            is_running = False
        except Exception as e:
            print(f"Loop encountered an error: {e}")
            is_running = False

# Command: Stop streaming text blocks
@bot.command(name="stop")
async def stop_payload(ctx):
    global is_running
    
    if not is_running:
        await ctx.send("❌ Transmission loop is already completely stopped.")
        return
        
    is_running = False
    await ctx.send("🛑 Transmission loop terminated safely.")

# 3. Execution Pipeline
if __name__ == "__main__":
    # Start the web server in a side thread so it doesn't block the Discord bot
    server_thread = Thread(target=run_web_server)
    server_thread.start()

    # Pull the token securely from Render's Environment Panel
    BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
    if not BOT_TOKEN:
        print("CRITICAL ERROR: 'DISCORD_TOKEN' environment variable is missing!")
    else:
        bot.run(BOT_TOKEN)
