import discord
from discord.ext import commands
import asyncio
from datetime import timedelta, datetime
import random
import aiohttp
import json
import os

# Bot setup with multiple prefixes
def get_prefix(bot, message):
    return ['!', '/', '?']

TOKEN = os.getenv("TOKEN")

bot = commands.Bot(command_prefix=get_prefix, intents=discord.Intents.all(), help_command=None)

AUTOROLE_ID = None
WELCOME_CHANNEL_ID = None
LEAVE_CHANNEL_ID = None
LOG_CHANNEL_ID = None
SUGGESTION_CHANNEL_ID = None
LEVELS = {}
XPER_POINTS = {}

# ========== EVENTS ==========

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is now online!")
    print(f"Bot is in {len(bot.guilds)} servers")
    await bot.change_presence(activity=discord.Game(name="!help | ConfigBot"))

@bot.event
async def on_member_join(member):
    if AUTOROLE_ID:
        role = member.guild.get_role(AUTOROLE_ID)
        if role:
            await member.add_roles(role)
            print(f"Gave {member} the {role.name} role")
    
    if WELCOME_CHANNEL_ID:
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="✨ Welcome to the server! ✨",
                description=f"Hey {member.mention}, thanks for joining **{member.guild.name}**!\n\nPlease read the rules and enjoy your stay.",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Member #{len(member.guild.members)}")
            await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    if LEAVE_CHANNEL_ID:
        channel = member.guild.get_channel(LEAVE_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="👋 Goodbye!",
                description=f"{member.name} left the server.",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

# ========== UTILITY COMMANDS ==========

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command()
async def test(ctx):
    """Test if bot is working"""
    await ctx.send("✅ ConfigBot is working!")

@bot.command()
async def hello(ctx):
    """Say hello"""
    await ctx.send(f"👋 Hello {ctx.author.mention}!")

@bot.command()
async def info(ctx):
    """Bot information"""
    embed = discord.Embed(
        title="⚙️ ConfigBot",
        description="The all-in-one Discord bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="Servers", value=f"{len(bot.guilds)}", inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Commands", value="`!help`", inline=True)
    embed.add_field(name="Creator", value="BrownMunda", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """Get a user's avatar"""
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    """Get server information"""
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, description="Server Information", color=discord.Color.green())
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """Get user information"""
    member = member or ctx.author
    embed = discord.Embed(title=member.name, color=discord.Color.blue())
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%b %d, %Y"), inline=True)
    embed.add_field(name="Joined Discord", value=member.created_at.strftime("%b %d, %Y"), inline=True)
    embed.add_field(name="Roles", value=", ".join([role.mention for role in member.roles[1:10]]), inline=False)
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def poll(ctx, question, *options):
    """Create a poll (use quotes for question)"""
    if len(options) < 2:
        await ctx.send("❌ You need at least 2 options!")
        return
    if len(options) > 10:
        await ctx.send("❌ Max 10 options!")
        return
    
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    description = []
    for i, option in enumerate(options):
        description.append(f"{emojis[i]} {option}")
    
    embed = discord.Embed(title=f"📊 {question}", description="\n".join(description), color=discord.Color.blue())
    embed.set_footer(text=f"Poll by {ctx.author.name}")
    msg = await ctx.send(embed=embed)
    
    for i in range(len(options)):
        await msg.add_reaction(emojis[i])

@bot.command()
async def choose(ctx, *choices):
    """Choose between options"""
    if len(choices) < 2:
        await ctx.send("❌ Give me at least 2 options separated by spaces!")
        return
    await ctx.send(f"🤔 I choose: **{random.choice(choices)}**")

@bot.command()
async def roll(ctx, dice: str = "1d6"):
    """Roll dice (e.g., 2d20)"""
    try:
        count, sides = map(int, dice.split('d'))
        if count > 100:
            await ctx.send("❌ Too many dice (max 100)")
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        await ctx.send(f"🎲 Rolling {dice}: **{total}** | ({', '.join(map(str, rolls))})")
    except:
        await ctx.send("❌ Use format like: `!roll 2d20`")

@bot.command()
async def flip(ctx):
    """Flip a coin"""
    result = random.choice(["Heads", "Tails"])
    await ctx.send(f"🪙 Coin flip: **{result}**")

@bot.command()
async def invite(ctx):
    """Get bot invite link"""
    embed = discord.Embed(
        title="📨 Invite ConfigBot",
        description="[Click here to invite ConfigBot to your server](https://discord.com/api/oauth2/authorize?client_id=1502478610814992404&permissions=8&scope=bot%20applications.commands)",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def uptime(ctx):
    """Bot uptime"""
    current_time = datetime.now()
    delta = current_time - bot.start_time if hasattr(bot, 'start_time') else timedelta(seconds=0)
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    seconds = delta.seconds % 60
    await ctx.send(f"⏰ Uptime: {hours}h {minutes}m {seconds}s")

# ========== MODERATION COMMANDS ==========

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kick a member"""
    await member.kick(reason=reason)
    embed = discord.Embed(title="👢 Kicked", description=f"{member.mention} has been kicked.\nReason: {reason}", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """Ban a member"""
    await member.ban(reason=reason)
    embed = discord.Embed(title="🔨 Banned", description=f"{member.mention} has been banned.\nReason: {reason}", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member):
    """Unban a member (use: !unban username#1234)"""
    banned_users = [entry async for entry in ctx.guild.bans()]
    member_name, member_discriminator = member.split('#')
    
    for ban_entry in banned_users:
        user = ban_entry.user
        if (user.name, user.discriminator) == (member_name, member_discriminator):
            await ctx.guild.unban(user)
            embed = discord.Embed(title="✅ Unbanned", description=f"{user.mention} has been unbanned.", color=discord.Color.green())
            await ctx.send(embed=embed)
            return
    await ctx.send("❌ User not found")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    """Clear messages (default 5, max 100)"""
    if amount > 100:
        await ctx.send("❌ Can only clear up to 100 messages at a time")
        return
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"✅ Cleared {amount} messages")
    await asyncio.sleep(2)
    await msg.delete()

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    """Lock a channel for @everyone"""
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔒 Locked {channel.mention}")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    """Unlock a channel"""
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(f"🔓 Unlocked {channel.mention}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    """Timeout a member (!timeout @user 10 spamming)"""
    duration = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"⏰ Timed out {member.mention} for {minutes} minutes | Reason: {reason}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    """Warn a member (creates a warning log)"""
    embed = discord.Embed(title="⚠️ Warning", description=f"{member.mention} has been warned.\nReason: {reason}", color=discord.Color.orange())
    embed.set_footer(text=f"Warned by {ctx.author.name}")
    await ctx.send(embed=embed)
    try:
        await member.send(f"⚠️ You were warned in {ctx.guild.name} for: {reason}")
    except:
        pass

@bot.command()
@commands.has_permissions(administrator=True)
async def slowmode(ctx, seconds: int):
    """Set slowmode for current channel"""
    if seconds > 21600:
        await ctx.send("❌ Slowmode can't be longer than 6 hours (21600 seconds)")
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"⏱️ Slowmode set to {seconds} seconds")

# ========== WELCOME & GOODBYE SETUP ==========

@bot.command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):
    """Set welcome channel"""
    global WELCOME_CHANNEL_ID
    WELCOME_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Welcome messages will be sent to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setleave(ctx, channel: discord.TextChannel):
    """Set leave channel"""
    global LEAVE_CHANNEL_ID
    LEAVE_CHANNEL_ID = channel.id
    await ctx.send(f"✅ Leave messages will be sent to {channel.mention}")

# ========== AUTO-ROLE COMMANDS ==========

@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, role: discord.Role):
    """Set the auto-role for new members"""
    global AUTOROLE_ID
    AUTOROLE_ID = role.id
    await ctx.send(f"✅ New members will automatically get {role.mention}")

# ========== FUN COMMANDS ==========

@bot.command()
async def meme(ctx):
    """Get a random meme"""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as resp:
            data = await resp.json()
            embed = discord.Embed(title=data["title"], color=discord.Color.blue())
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"👍 {data['ups']} upvotes")
            await ctx.send(embed=embed)

@bot.command()
async def dm(ctx, member: discord.Member, *, message):
    """DM a user (Admin only)"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only admins can use this command")
        return
    try:
        await member.send(f"📨 Message from {ctx.author.name}: {message}")
        await ctx.send(f"✅ Sent DM to {member.name}")
    except:
        await ctx.send("❌ Could not DM that user (DMs may be closed)")

# ========== HELP COMMAND ==========

@bot.command()
async def help(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title="⚙️ ConfigBot Commands",
        description="Use `!`, `/`, or `?` before commands\nExample: `!ping`",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="📌 Utility",
        value="`ping` `test` `hello` `info` `avatar` `serverinfo` `userinfo` `poll` `choose` `roll` `flip` `invite` `uptime`",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value="`kick @user` `ban @user` `unban user#1234` `clear 10` `lock` `unlock` `timeout @user 10` `warn @user` `slowmode 5`",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Setup",
        value="`setautorole @Role` `setwelcome #channel` `setleave #channel`",
        inline=False
    )
    
    embed.add_field(
        name="🎉 Fun",
        value="`meme`",
        inline=False
    )
    
    embed.add_field(
        name="⚡ Quick Start",
        value="1. Type `!test` to see if I'm alive\n2. Type `!setautorole @Member` to set auto-role\n3. Type `!lock` to lock a channel",
        inline=False
    )
    
    embed.set_footer(text="ConfigBot • Made with ❤️ by BrownMunda")
    await ctx.send(embed=embed)

# ========== ERROR HANDLING ==========

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Type `!help` for usage")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Couldn't find that member")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send(f"❌ Error: {error}")

# ========== RUN BOT ==========
bot.start_time = datetime.now()
bot.run(TOKEN)