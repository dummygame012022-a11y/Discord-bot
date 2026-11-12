import os
import sys
import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
API = os.getenv("API_URL", "http://127.0.0.1:5060")


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if 'sync' in sys.argv:
            await self.tree.sync()


bot = Bot()


@bot.event
async def on_ready():
    print("Online as", bot.user)


@bot.tree.command(name="ping", description="Test kung buhi ang bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send("Pong")


@bot.tree.command(name="verify", description="Check imong membership")
async def verify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    url = f"{API}/api/membership/{interaction.user.id}"
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                data = await r.json()
    except Exception:
        await interaction.followup.send("API error. Try again later.")
        return
    if data.get("active"):
        e = discord.Embed(title="Membership active", color=0x22C55E)
        e.add_field(name="Plan", value=data.get("plan", "-"))
        e.add_field(name="Expires", value=data.get("expires", "-"))
    else:
        e = discord.Embed(title="No active membership", color=0xEF4444)
    await interaction.followup.send(embed=e)


@bot.tree.command(name="search", description="Search products")
@app_commands.describe(query="Product name, e.g. mouse")
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(f"{API}/api/products", params={"q": query}) as r:
                data = await r.json()
    except Exception:
        await interaction.followup.send("API error. Try again later.")
        return
    items = data.get("items", [])
    if not items:
        await interaction.followup.send(f"No results for: {query}")
        return
    e = discord.Embed(title=f"Results for: {query}", color=0x3B82F6)
    for p in items:
        stock = "In stock" if p["stock"] > 0 else "Out of stock"
        e.add_field(name=p["name"], value=f"${p['price']:.2f} - {stock}", inline=False)
    await interaction.followup.send(embed=e)


bot.run(TOKEN)
