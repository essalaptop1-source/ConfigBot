import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import re
import base64
import math
import time
import os
from collections import defaultdict

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

cooldowns = defaultdict(dict)

class Deobfuscator:
    @staticmethod
    def decode_string_fromchar(match):
        content = match.group(1)
        try:
            numbers = re.findall(r'\d+', content)
            chars = [chr(int(num)) for num in numbers]
            return ''.join(chars)
        except:
            return match.group(0)
    
    @staticmethod
    def decode_char(match):
        content = match.group(1)
        try:
            numbers = re.findall(r'\d+', content)
            chars = [chr(int(num)) for num in numbers]
            return ''.join(chars)
        except:
            return match.group(0)
    
    @staticmethod
    def decode_hex_escapes(text):
        def replace_hex(match):
            hex_val = match.group(1)
            try:
                return chr(int(hex_val, 16))
            except:
                return match.group(0)
        return re.sub(r'\\x([0-9a-fA-F]{2})', replace_hex, text)
    
    @staticmethod
    def remove_loadstring_wrappers(text):
        patterns = [
            r'loadstring\s*\(\s*"([^"]+)"\s*\)\s*\(\s*\)',
            r'loadstring\s*\(\s*\'([^\']+)\'\s*\)\s*\(\s*\)',
            r'loadstring\s*\(([^)]+)\)\s*\(\s*\)'
        ]
        
        for pattern in patterns:
            while True:
                match = re.search(pattern, text, re.IGNORECASE)
                if not match:
                    break
                if len(match.groups()) > 0:
                    content = match.group(1)
                    text = text.replace(match.group(0), content)
                else:
                    text = text.replace(match.group(0), "")
        
        return text
    
    @staticmethod
    def deobfuscate_lua(script):
        original = script
        max_passes = 5
        
        for _ in range(max_passes):
            script = Deobfuscator.remove_loadstring_wrappers(script)
            
            script = re.sub(
                r'String\.fromCharCode\s*\(\s*([^)]+)\s*\)',
                Deobfuscator.decode_string_fromchar,
                script
            )
            
            script = re.sub(
                r'Char\s*\(\s*([^)]+)\s*\)',
                Deobfuscator.decode_char,
                script
            )
            
            script = Deobfuscator.decode_hex_escapes(script)
            
            script = re.sub(r'\s+', ' ', script)
            script = re.sub(r'\n\s*\n', '\n', script)
            
            if script == original:
                break
            original = script
        
        return script

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
        print(f"{bot.user} is ready!")
    except Exception as e:
        print(f"Error syncing commands: {e}")

def check_cooldown(user_id):
    current_time = time.time()
    if user_id in cooldowns:
        last_used = cooldowns[user_id].get('last_used', 0)
        if current_time - last_used < 30:
            return 30 - (current_time - last_used)
    return 0

def update_cooldown(user_id):
    cooldowns[user_id]['last_used'] = time.time()

async def send_long_message(interaction, content):
    """Send long messages by splitting into multiple Discord messages"""
    if not content or content.isspace():
        await interaction.followup.send("❌ No output to display.")
        return
    
    limit = 1900  # Discord's limit is 2000, using 1900 for safety
    prefix = "```lua\n"
    suffix = "\n```"
    
    # If content fits in one message
    if len(content) + len(prefix) + len(suffix) <= limit:
        await interaction.followup.send(f"{prefix}{content}{suffix}")
        return
    
    # Split content into chunks
    chunks = []
    lines = content.split('\n')
    current_chunk = ""
    
    for line in lines:
        # Check if adding this line would exceed the limit
        test_chunk = current_chunk + line + "\n"
        if len(test_chunk) + len(prefix) + len(suffix) <= limit:
            current_chunk = test_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk.rstrip('\n'))
            current_chunk = line + "\n"
    
    if current_chunk:
        chunks.append(current_chunk.rstrip('\n'))
    
    # Send each chunk
    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.followup.send(f"{prefix}{chunk}{suffix}")
        else:
            await interaction.followup.send(f"{prefix}{chunk}{suffix}")

@bot.tree.command(name="deobfuscate", description="Deobfuscate Lua code")
@app_commands.describe(script="The Lua script to deobfuscate")
async def deobfuscate(interaction: discord.Interaction, script: str):
    await interaction.response.defer()
    
    cooldown_left = check_cooldown(interaction.user.id)
    if cooldown_left > 0:
        await interaction.followup.send(f"⏰ Please wait {cooldown_left:.1f} seconds.")
        return
    
    if len(script) > 50000:
        await interaction.followup.send("❌ Script too long. Maximum 50,000 characters.")
        return
    
    try:
        deobfuscated = Deobfuscator.deobfuscate_lua(script)
        
        if not deobfuscated or deobfuscated.isspace():
            await interaction.followup.send("❌ No valid Lua code found.")
            return
        
        update_cooldown(interaction.user.id)
        await send_long_message(interaction, deobfuscated)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="deobf_upload", description="Upload a .lua file to deobfuscate")
async def deobf_upload(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer()
    
    cooldown_left = check_cooldown(interaction.user.id)
    if cooldown_left > 0:
        await interaction.followup.send(f"⏰ Please wait {cooldown_left:.1f} seconds.")
        return
    
    if not file.filename.endswith('.lua'):
        await interaction.followup.send("❌ Please upload a .lua file.")
        return
    
    # Discord free limit is 25MB (25,000,000 bytes)
    if file.size > 25000000:
        await interaction.followup.send("❌ File too large. Maximum 25MB.")
        return
    
    try:
        content_bytes = await file.read()
        script = content_bytes.decode('utf-8', errors='ignore')
        
        deobfuscated = Deobfuscator.deobfuscate_lua(script)
        
        if not deobfuscated or deobfuscated.isspace():
            await interaction.followup.send("❌ No valid Lua code found.")
            return
        
        update_cooldown(interaction.user.id)
        await send_long_message(interaction, deobfuscated)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    bot.run(TOKEN)