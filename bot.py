import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import requests
import json
import re
from urllib.parse import urlparse, parse_qs
import base64
from typing import Dict, List, Optional
import asyncio
import aiohttp
import gzip
import sqlite3
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

class BungieAPIClient:
    """Enhanced client for interacting with the Bungie API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.bungie.net/Platform"
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        self.manifest_data = None
        self.item_definitions = {}
        self.plug_definitions = {}
        self.stat_definitions = {}
        self.damage_type_definitions = {}
        self.subclass_definitions = {}
        self.perk_definitions = {}

        # Cache for API responses
        self.cache = {}
        self.cache_duration = timedelta(hours=1)

    async def initialize(self):
        """Initialize the API client by fetching manifest data"""
        try:
            await self._fetch_manifest()
            await self._fetch_essential_definitions()
            print("✅ Bungie API initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize Bungie API: {e}")
            return False

    async def _fetch_manifest(self):
        """Fetch the Destiny 2 manifest"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/Destiny2/Manifest/", headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.manifest_data = data["Response"]
                        print("✅ Manifest fetched successfully")
                    else:
                        print(f"❌ Failed to fetch manifest: {response.status}")
                        raise Exception(f"Manifest fetch failed with status {response.status}")
            except Exception as e:
                print(f"❌ Error fetching manifest: {e}")
                raise

    async def _fetch_essential_definitions(self):
        """Fetch essential item definitions"""
        if not self.manifest_data:
            return

        try:
            definitions_to_fetch = {
                "item_definitions": "DestinyInventoryItemDefinition",
                "stat_definitions": "DestinyStatDefinition",
                "damage_type_definitions": "DestinyDamageTypeDefinition",
                "subclass_definitions": "DestinySubclassDefinition",
                "perk_definitions": "DestinyPerkDefinition"
            }

            async with aiohttp.ClientSession() as session:
                for attr_name, definition_name in definitions_to_fetch.items():
                    try:
                        url = self.manifest_data["jsonWorldComponentContentPaths"]["en"][definition_name]
                        full_url = f"https://www.bungie.net{url}"

                        async with session.get(full_url, headers=self.headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                setattr(self, attr_name, data)
                                print(f"✅ {definition_name} loaded ({len(data)} items)")
                            else:
                                print(f"⚠️ Failed to load {definition_name}: {response.status}")
                    except Exception as e:
                        print(f"⚠️ Error loading {definition_name}: {e}")

        except Exception as e:
            print(f"❌ Error fetching definitions: {e}")

    def get_item_info(self, item_hash: str) -> Optional[Dict]:
        """Get item information from hash"""
        try:
            # Handle negative hashes (convert to unsigned 32-bit)
            if isinstance(item_hash, int) and item_hash < 0:
                item_hash = str(item_hash & 0xFFFFFFFF)
            else:
                item_hash = str(item_hash)

            if item_hash in self.item_definitions:
                return self.item_definitions[item_hash]
            return None
        except Exception as e:
            print(f"❌ Error getting item info for hash {item_hash}: {e}")
            return None

    def get_weapon_stats(self, item_hash: str) -> Dict:
        """Get weapon stats from item hash"""
        try:
            item_info = self.get_item_info(item_hash)
            if not item_info:
                return {}

            stats = {}
            if "stats" in item_info and "stats" in item_info["stats"]:
                for stat_hash, stat_value in item_info["stats"]["stats"].items():
                    stat_info = self.stat_definitions.get(stat_hash, {})
                    stat_name = stat_info.get("displayProperties", {}).get("name", "Unknown")
                    stats[stat_name] = stat_value.get("value", 0)

            return stats
        except Exception as e:
            print(f"❌ Error getting weapon stats: {e}")
            return {}

    def get_damage_type_name(self, damage_type_hash: str) -> str:
        """Get damage type name from hash"""
        try:
            damage_info = self.damage_type_definitions.get(str(damage_type_hash), {})
            return damage_info.get("displayProperties", {}).get("name", "Unknown")
        except Exception as e:
            return "Unknown"

    def get_weapon_type(self, item_hash: str) -> str:
        """Get weapon type from item hash"""
        try:
            item_info = self.get_item_info(item_hash)
            if item_info:
                return item_info.get("itemTypeDisplayName", "Unknown")
            return "Unknown"
        except Exception as e:
            return "Unknown"

    def is_exotic(self, item_hash: str) -> bool:
        """Check if item is exotic"""
        try:
            item_info = self.get_item_info(item_hash)
            if item_info:
                return item_info.get("inventory", {}).get("tierType", 0) == 6
            return False
        except Exception as e:
            return False

    def _get_weapon_info(self, item_hash: str) -> Optional[Dict]:
        """Get weapon information from hash"""
        try:
            item_info = self.bungie_client.get_item_info(item_hash)
            if not item_info:
                return None

            display_props = item_info.get("displayProperties", {})

            return {
                "hash": item_hash,
                "name": display_props.get("name", "Unknown"),
                "type": self.bungie_client.get_weapon_type(item_hash),
                "element": self._get_damage_type(item_info),
                "is_exotic": self.bungie_client.is_exotic(item_hash),
                "stats": self.bungie_client.get_weapon_stats(item_hash)
            }
        except Exception as e:
            print(f"❌ Error getting weapon info: {e}")
            return None

    def _get_damage_type(self, item_info: Dict) -> str:
        """Extract damage type from item info"""
        try:
            damage_type_hash = item_info.get("defaultDamageType", 0)
            return self.bungie_client.get_damage_type_name(damage_type_hash)
        except Exception as e:
            return "Unknown"

   

@bot.command(name='gr')
async def god_roll_finder(ctx, weapon_type: str):
    """Find god rolls for a specific weapon type"""
    if not bungie_client:
        await ctx.send("❌ Bungie API not available")
        return

    # Send initial message with menu
    message = await ctx.send(
        f"🔍 **God Roll Finder for {weapon_type}**\n\n"
        "React with the following emojis to add parameters or start the search:\n\n"
        "🔫 - Add Archetype\n"
        "🔥 - Add Element\n"
        "✨ - Add Traits\n"
        "🔄 - Start Search"
    )

    # Add reactions to the message
    await message.add_reaction("🔫")
    await message.add_reaction("🔥")
    await message.add_reaction("✨")
    await message.add_reaction("🔄")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["🔫", "🔥", "✨", "🔄"]

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)

        if str(reaction.emoji) == "🔫":
            await ctx.send("Please specify the archetype.")
            # Add logic to handle archetype input
        elif str(reaction.emoji) == "🔥":
            await ctx.send("Please specify the element.")
            # Add logic to handle element input
        elif str(reaction.emoji) == "✨":
            await ctx.send("Please specify the traits.")
            # Add logic to handle traits input
        elif str(reaction.emoji) == "🔄":
            await ctx.send(f"Searching for god rolls for {weapon_type}...")
            # Add logic to perform the search and return results

    except asyncio.TimeoutError:
        await ctx.send("⏰ You took too long to respond. Please try again.")



@bot.command(name='weapon')
async def weapon_lookup(ctx, *, weapon_name: str = None):
    """Look up detailed information about a specific weapon"""
    if not bungie_client:
        await ctx.send("❌ Bungie API not available")
        return

    if not weapon_name:
        await ctx.send("❌ Please provide a weapon name: `!weapon <weapon_name>`")
        return

    try:
        # Search for weapons matching the name
        matching_weapons = []
        search_term = weapon_name.lower()

        for item_hash, item_data in bungie_client.item_definitions.items():
            if item_data.get("itemType") == 3:  # Weapon type
                item_name = item_data.get("displayProperties", {}).get("name", "").lower()
                if search_term in item_name:
                    matching_weapons.append((item_hash, item_data))

        if not matching_weapons:
            embed = discord.Embed(
                title="❌ Weapon Not Found",
                description=f"No weapons found matching '{weapon_name}'",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return

        # Get the first match (most relevant)
        weapon_hash, weapon_data = matching_weapons[0]
        weapon_info = bungie_client.get_item_info(weapon_hash)
        weapon_stats = bungie_client.get_weapon_stats(weapon_hash)

        display_props = weapon_data.get("displayProperties", {})
        weapon_name = display_props.get("name", "Unknown")
        weapon_type = weapon_data.get("itemTypeDisplayName", "Unknown")
        is_exotic = bungie_client.is_exotic(weapon_hash)

        embed = discord.Embed(
            title=f"🔫 {weapon_name}",
            description=f"**Type:** {weapon_type}\n**Rarity:** {'Exotic' if is_exotic else 'Legendary'}",
            color=0xffa500 if is_exotic else 0x9932cc
        )

        # Add stats
        if weapon_stats:
            stats_text = []
            for stat, value in weapon_stats.items():
                stats_text.append(f"**{stat}:** {value}")
            embed.add_field(name="📊 Base Stats", value="\n".join(stats_text), inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Lookup Error",
            description=f"Error looking up weapon: {str(e)}",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='status')
async def bot_status(ctx):
    """Check bot status and API connectivity"""
    embed = discord.Embed(title="🤖 Bot Status", color=0x0099ff)

    # Basic bot info
    embed.add_field(name="🏠 Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="👥 Users", value=len(bot.users), inline=True)
    embed.add_field(name="📡 Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)

    # API status
    api_status = "✅ Connected" if bungie_client else "❌ Not Connected"
    embed.add_field(name="🎯 Bungie API", value=api_status, inline=True)

    parser_status = "✅ Active" if dim_parser else "❌ Inactive"
    embed.add_field(name="🔗 DIM Parser", value=parser_status, inline=True)

    analyzer_status = "✅ Ready" if analyzer else "❌ Not Ready"
    embed.add_field(name="🧮 Build Analyzer", value=analyzer_status, inline=True)

    # Feature availability
    features = []
    if bungie_client and dim_parser and analyzer:
        features.append("✅ Real DIM link parsing")
        features.append("✅ Live weapon/armor data")
        features.append("✅ Advanced build analysis")
        features.append("✅ Exotic synergy detection")
    else:
        features.append("❌ Limited functionality")

    embed.add_field(name="🔧 Features", value="\n".join(features), inline=False)

    await ctx.send(embed=embed)

@bot.command(name='help_destiny')
async def help_destiny(ctx):
    """Comprehensive help for Destiny 2 build analysis"""
    embed = discord.Embed(
        title="🎯 Enhanced Destiny 2 Build Analyzer",
        description="Advanced build analysis using real-time Bungie API data and DIM link parsing!",
        color=0x0099ff
    )

    embed.add_field(
        name="📋 Commands",
        value="`!review <DIM_link>` - Analyze a build from DIM\n`!weapon <name>` - Look up weapon stats\n`!status` - Check bot status\n`!help_destiny` - Show this help",
        inline=False
    )

    embed.add_field(
        name="🔍 Analysis Features",
        value="• **Real DIM Link Parsing** - Extracts actual loadout data\n• **Live Weapon/Armor Stats** - Direct from Bungie API\n• **Synergy Detection** - Element, exotic, and stat synergies\n• **Comprehensive Rating** - 1-10 scale with detailed feedback",
        inline=False
    )

    embed.add_field(
        name="📊 What Gets Analyzed",
        value="• Weapon loadout and stats\n• Armor pieces and stat distribution\n• Subclass and elemental synergies\n• Exotic gear combinations\n• Stat tier optimization\n• Build balance and weaknesses",
        inline=False
    )

    embed.add_field(
        name="🔗 How to Use",
        value="1. Create a build in DIM (Destiny Item Manager)\n2. Copy the share link from DIM\n3. Use `!review <your_link>` in Discord\n4. Get detailed analysis with suggestions!",
        inline=False
    )

    embed.add_field(
        name="⚡ New Features",
        value="✅ Real-time data integration\n✅ Enhanced exotic synergy detection\n✅ Detailed stat tier analysis\n✅ Elemental coverage evaluation\n✅ Class-specific recommendations",
        inline=False
    )

    await ctx.send(embed=embed)

# Run the bot
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
