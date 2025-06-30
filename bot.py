import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')

@bot.command(name='hello')
async def hello(ctx):
    await ctx.send(f'Hello {ctx.author.mention}!')

@bot.command(name='ping')
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! Latency: {latency}ms')

@bot.command(name='info')
async def info(ctx):
    embed = discord.Embed(title="Bot Info", color=0x00ff00)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Users", value=len(bot.users), inline=True)
    await ctx.send(embed=embed)
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # When User sends any message, bot responds
    if message.author.id == 530400547610558514:
        await message.channel.send("🚨Alerte Possible second degré !!🚨")
    
    await bot.process_commands(message)

# Run the bot
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
