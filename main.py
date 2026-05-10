# main.py
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
from typing import Optional

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Rate limiting
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
    def decode_hex(match):
        hex_str = match.group(1)
        try:
            return bytes.fromhex(hex_str).decode('utf-8')
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
    def decode_base64_loadstring(match):
        b64_str = match.group(1).strip()
        try:
            decoded = base64.b64decode(b64_str).decode('utf-8')
            return decoded
        except:
            return match.group(0)
    
    @staticmethod
    def evaluate_simple_arithmetic(match):
        expr = match.group(1)
        try:
            expr = expr.replace('^', '**')
            result = eval(expr, {"__builtins__": {}}, {"math": math})
            return str(result)
        except:
            return match.group(0)
    
    @staticmethod
    def remove_loadstring_wrappers(text):
        patterns = [
            r'loadstring\s*\(\s*"([^"]+)"\s*\)\s*\(\s*\)',
            r'loadstring\s*\(\s*\'([^\']+)\'\s*\)\s*\(\s*\)',
            r'\(function\(\)\s*loadstring\s*\([^)]+\)\s*end\)\(\)',
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
            
            script = re.sub(
                r'\\"([0-9a-fA-F]+)\\"',
                Deobfuscator.decode_hex,
                script
            )
            
            script = Deobfuscator.decode_hex_escapes(script)
            
            script = re.sub(
                r'loadstring\s*\(\s*(?:base64\.decode\s*\()?"([A-Za-z0-9+/=]+)"',
                Deobfuscator.decode_base64_loadstring,
                script
            )
            
            script = re.sub(
                r'\[\[\s*([0-9+\-*/\s^().]+)\s*\]\]',
                Deobfuscator.evaluate_simple_arithmetic,
                script
            )
            
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
    if len(content) <= 1900:
        await interaction.followup.send(f"```lua\n{content}\n```")
        return
    
    chunks = []
    current_chunk = ""
    
    lines = content.split('\n')
    for line in lines:
        if len(current_chunk) + len(line) + 1 < 1900:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + '\n'
    
    if current_chunk:
        chunks.append(current_chunk)
    
    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.followup.send(f"```lua\n{chunk}\n```")
        else:
            await interaction.followup.send(f"```lua\n{chunk}\n```")

@bot.tree.command(name="deobfuscate", description="Deobfuscate Lua code")
@app_commands.describe(script="The Lua script to deobfuscate")
async def deobfuscate(interaction: discord.Interaction, script: str):
    await interaction.response.defer()
    
    cooldown_left = check_cooldown(interaction.user.id)
    if cooldown_left > 0:
        await interaction.followup.send(f"⏰ Please wait {cooldown_left:.1f} seconds before using this command again.")
        return
    
    if len(script) > 10000:
        await interaction.followup.send("❌ Script too long. Maximum length is 10,000 characters.")
        return
    
    try:
        deobfuscated = Deobfuscator.deobfuscate_lua(script)
        
        if not deobfuscated or deobfuscated.isspace():
            await interaction.followup.send("❌ No valid Lua code found or deobfuscation resulted in empty output.")
            return
        
        update_cooldown(interaction.user.id)
        await send_long_message(interaction, deobfuscated)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error during deobfuscation: {str(e)}")

@bot.tree.command(name="deobf_upload", description="Upload a .lua file to deobfuscate")
async def deobf_upload(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.defer()
    
    cooldown_left = check_cooldown(interaction.user.id)
    if cooldown_left > 0:
        await interaction.followup.send(f"⏰ Please wait {cooldown_left:.1f} seconds before using this command again.")
        return
    
    if not file.filename.endswith('.lua'):
        await interaction.followup.send("❌ Please upload a .lua file.")
        return
    
    if file.size > 5000000:
        await interaction.followup.send("❌ File too large. Maximum size is 50KB.")
        return
    
    try:
        content_bytes = await file.read()
        script = content_bytes.decode('utf-8', errors='ignore')
        
        deobfuscated = Deobfuscator.deobfuscate_lua(script)
        
        if not deobfuscated or deobfuscated.isspace():
            await interaction.followup.send("❌ No valid Lua code found or deobfuscation resulted in empty output.")
            return
        
        update_cooldown(interaction.user.id)
        await send_long_message(interaction, deobfuscated)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error processing file: {str(e)}")

# Error handling
@deobfuscate.error
async def deobfuscate_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
    else:
        await interaction.response.send_message("❌ An error occurred while processing the command.")

@deobf_upload.error
async def deobf_upload_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
    else:
        await interaction.response.send_message("❌ An error occurred while processing the file upload.")

if __name__ == "__main__":
    bot.run(TOKEN)