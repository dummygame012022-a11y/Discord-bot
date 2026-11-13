import os
import sys
import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
API = os.getenv("API_URL", "http://127.0.0.1:5060")
HEADERS = {"X-API-Key": os.getenv("API_KEY", "")}


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


async def fetch_membership(uid):
    timeout = aiohttp.ClientTimeout(total=5)
    async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as s:
        async with s.get(f"{API}/api/membership/{uid}") as r:
            if r.status == 401:
                raise RuntimeError("bad api key")
            return await r.json()


def verify_embed(data):
    if data.get("active"):
        e = discord.Embed(title="Membership active", color=0x22C55E)
        e.add_field(name="Plan", value=data.get("plan", "-"))
        e.add_field(name="Expires", value=data.get("expires", "-"))
    else:
        e = discord.Embed(title="No active membership", color=0xEF4444)
    return e


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            data = await fetch_membership(interaction.user.id)
        except Exception:
            await interaction.followup.send("API error.", ephemeral=True)
            return
        await interaction.edit_original_response(embed=verify_embed(data), view=self)


@bot.tree.command(name="verify", description="Check imong membership")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
async def verify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        data = await fetch_membership(interaction.user.id)
    except Exception:
        await interaction.followup.send("API error. Try again later.")
        return
    await interaction.followup.send(embed=verify_embed(data), view=VerifyView())


PER_PAGE = 3


class SearchView(discord.ui.View):
    def __init__(self, query, items):
        super().__init__(timeout=120)
        self.query = query
        self.items = items
        self.page = 0
        self.pages = max(1, (len(items) + PER_PAGE - 1) // PER_PAGE)
        self.sync()

    def chunk(self):
        start = self.page * PER_PAGE
        return start, self.items[start:start + PER_PAGE]

    def sync(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.pages - 1
        start, part = self.chunk()
        self.pick.options = [
            discord.SelectOption(label=str(p["name"])[:100], value=str(start + i))
            for i, p in enumerate(part)
        ]

    def embed(self):
        e = discord.Embed(title=f"Results for: {self.query}", color=0x3B82F6)
        for p in self.chunk()[1]:
            stock = "In stock" if p["stock"] > 0 else "Out of stock"
            e.add_field(name=p["name"], value=f"${p['price']:.2f} - {stock}", inline=False)
        e.set_footer(text=f"Page {self.page + 1}/{self.pages}")
        return e

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self.sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self.sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.select(placeholder="Pili og product", options=[discord.SelectOption(label="-", value="0")])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.Select):
        p = self.items[int(select.values[0])]
        e = discord.Embed(title=p["name"], color=0x3B82F6)
        e.add_field(name="Price", value=f"${p['price']:.2f}")
        e.add_field(name="Stock", value=str(p["stock"]))
        await interaction.response.send_message(embed=e, ephemeral=True)


@bot.tree.command(name="search", description="Search products")
@app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
@app_commands.describe(query="Product name, e.g. mouse")
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as s:
            async with s.get(f"{API}/api/products", params={"q": query}) as r:
                if r.status == 401:
                    raise RuntimeError("bad api key")
                data = await r.json()
    except Exception:
        await interaction.followup.send("API error. Try again later.")
        return
    items = data.get("items", [])
    if not items:
        await interaction.followup.send(f"No results for: {query}")
        return
    view = SearchView(query, items)
    await interaction.followup.send(embed=view.embed(), view=view)


import logging
log = logging.getLogger("bot")


@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Hulat og {int(error.retry_after) + 1} segundos."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "Admin ra ang pwede ani."
    else:
        log.error("Command error: %s", error, exc_info=error)
        msg = "Naay error. Try again later."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        log.warning("Could not send error message")


@bot.tree.command(name="stats", description="Admin: bot stats")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.checks.has_permissions(administrator=True)
async def stats(interaction: discord.Interaction):
    ms = round(bot.latency * 1000)
    text = f"Servers: {len(bot.guilds)}\nLatency: {ms} ms"
    await interaction.response.send_message(text, ephemeral=True)


bot.run(TOKEN)
