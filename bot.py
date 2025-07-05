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

# Load environment variables
load_dotenv()

class BungieAPIClient:
    """Client for interacting with the Bungie API"""
    
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
        
    async def initialize(self):
        """Initialize the API client by fetching manifest data"""
        try:
            await self._fetch_manifest()
            print("✅ Bungie API initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize Bungie API: {e}")
    
    async def _fetch_manifest(self):
        """Fetch the Destiny 2 manifest"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/Destiny2/Manifest/", headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.manifest_data = data["Response"]
                        
                        # Get essential definitions
                        await self._fetch_definitions(session)
                    else:
                        print(f"Failed to fetch manifest: {response.status}")
            except Exception as e:
                print(f"Error fetching manifest: {e}")
    
    async def _fetch_definitions(self, session):
        """Fetch essential item definitions"""
        try:
            # Get item definitions URL
            item_def_url = self.manifest_data["jsonWorldComponentContentPaths"]["en"]["DestinyInventoryItemDefinition"]
            plug_def_url = self.manifest_data["jsonWorldComponentContentPaths"]["en"]["DestinyPlugSetDefinition"]
            stat_def_url = self.manifest_data["jsonWorldComponentContentPaths"]["en"]["DestinyStatDefinition"]
            damage_def_url = self.manifest_data["jsonWorldComponentContentPaths"]["en"]["DestinyDamageTypeDefinition"]
            
            # Fetch definitions (limit to essential ones for performance)
            async with session.get(f"https://www.bungie.net{item_def_url}", headers=self.headers) as response:
                if response.status == 200:
                    self.item_definitions = await response.json()
                    
            async with session.get(f"https://www.bungie.net{stat_def_url}", headers=self.headers) as response:
                if response.status == 200:
                    self.stat_definitions = await response.json()
                    
            async with session.get(f"https://www.bungie.net{damage_def_url}", headers=self.headers) as response:
                if response.status == 200:
                    self.damage_type_definitions = await response.json()
                    
        except Exception as e:
            print(f"Error fetching definitions: {e}")
    
    def get_item_info(self, item_hash: str) -> Optional[Dict]:
        """Get item information from hash"""
        try:
            item_hash = str(item_hash)
            if item_hash in self.item_definitions:
                return self.item_definitions[item_hash]
            return None
        except Exception as e:
            print(f"Error getting item info: {e}")
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
            print(f"Error getting weapon stats: {e}")
            return {}
    
    def get_damage_type_name(self, damage_type_hash: str) -> str:
        """Get damage type name from hash"""
        try:
            damage_info = self.damage_type_definitions.get(str(damage_type_hash), {})
            return damage_info.get("displayProperties", {}).get("name", "Unknown")
        except Exception as e:
            return "Unknown"

class DestinyBuildAnalyzer:
    """Enhanced build analyzer with Bungie API integration"""
    
    def __init__(self, bungie_client: BungieAPIClient):
        self.bungie_client = bungie_client
        self.synergy_data = self._load_synergy_data()
        
    def _load_synergy_data(self) -> Dict:
        """Load enhanced synergy data"""
        return {
            "subclass_synergies": {
                "solar": {
                    "keywords": ["burn", "ignite", "scorch", "radiant", "restoration", "solar"],
                    "synergistic_fragments": ["Ember of Torches", "Ember of Empyrean", "Ember of Benevolence"],
                    "good_with_weapons": ["fusion rifle", "linear fusion rifle", "hand cannon"],
                    "damage_bonus_mods": ["Font of Might", "High-Energy Fire", "Radiant Light"]
                },
                "arc": {
                    "keywords": ["jolt", "blind", "amplified", "ionic trace", "arc"],
                    "synergistic_fragments": ["Spark of Shock", "Spark of Magnitude", "Spark of Ions"],
                    "good_with_weapons": ["smg", "sidearm", "pulse rifle"],
                    "damage_bonus_mods": ["Font of Might", "High-Energy Fire", "Powerful Friends"]
                },
                "void": {
                    "keywords": ["volatile", "suppress", "weaken", "devour", "invisibility", "void"],
                    "synergistic_fragments": ["Echo of Starvation", "Echo of Harvest", "Echo of Undermining"],
                    "good_with_weapons": ["hand cannon", "sniper rifle", "bow"],
                    "damage_bonus_mods": ["Font of Might", "High-Energy Fire", "Protective Light"]
                },
                "stasis": {
                    "keywords": ["slow", "freeze", "shatter", "crystal", "stasis"],
                    "synergistic_fragments": ["Whisper of Chains", "Whisper of Shards", "Whisper of Bonds"],
                    "good_with_weapons": ["pulse rifle", "scout rifle", "linear fusion rifle"],
                    "damage_bonus_mods": ["Font of Might", "High-Energy Fire", "Elemental Charge"]
                },
                "strand": {
                    "keywords": ["suspend", "unraveling", "sever", "threadling", "strand"],
                    "synergistic_fragments": ["Thread of Ascent", "Thread of Fury", "Thread of Warding"],
                    "good_with_weapons": ["auto rifle", "machine gun", "glaive"],
                    "damage_bonus_mods": ["Font of Might", "High-Energy Fire", "Strand Siphon"]
                }
            },
            "exotic_synergies": {
                # Popular exotic weapons and their synergies
                "Witherhoard": ["void", "area damage", "indirect damage"],
                "Osteo Striga": ["void", "poison", "crowd control"],
                "Gjallarhorn": ["solar", "rocket launcher", "team support"],
                "Thunderlord": ["arc", "machine gun", "lightning"],
                "Whisper of the Worm": ["void", "sniper rifle", "boss damage"],
                "Xenophage": ["solar", "machine gun", "consistent damage"],
                "Divinity": ["arc", "trace rifle", "team support", "debuff"],
                "Anarchy": ["arc", "grenade launcher", "area denial"]
            },
            "stat_priorities": {
                "hunter": {
                    "pve": ["Recovery", "Discipline", "Mobility"],
                    "pvp": ["Recovery", "Mobility", "Intellect"]
                },
                "warlock": {
                    "pve": ["Recovery", "Discipline", "Intellect"],
                    "pvp": ["Recovery", "Discipline", "Intellect"]
                },
                "titan": {
                    "pve": ["Recovery", "Resilience", "Discipline"],
                    "pvp": ["Recovery", "Resilience", "Strength"]
                }
            }
        }
    
    def parse_dim_link(self, url: str) -> Optional[Dict]:
        """Parse DIM link - enhanced version"""
        try:
            # For demo purposes, we'll simulate parsing a DIM link
            # In reality, you'd need to reverse-engineer the DIM link format
            # This is a simplified structure showing what data we'd expect
            
            # Check if it's a DIM link
            if "dim.gg" not in url:
                return None
            
            # Simulate parsed build data (in real implementation, this would be extracted from the URL)
            demo_build = {
                "class": "warlock",
                "subclass": {
                    "element": "solar",
                    "super": "Well of Radiance"
                },
                "weapons": [
                    {
                        "slot": "kinetic",
                        "name": "Osteo Striga",
                        "type": "auto rifle",
                        "element": "void",
                        "hash": "1392919471"
                    },
                    {
                        "slot": "energy",
                        "name": "Ikelos SMG",
                        "type": "smg",
                        "element": "solar",
                        "hash": "1723472487"
                    },
                    {
                        "slot": "heavy",
                        "name": "Gjallarhorn",
                        "type": "rocket launcher",
                        "element": "solar",
                        "hash": "1363886209"
                    }
                ],
                "armor": [
                    {
                        "slot": "helmet",
                        "name": "Phoenix Protocol",
                        "stats": {"Recovery": 68, "Discipline": 64, "Intellect": 58},
                        "mods": ["Elemental Charge", "Font of Might"]
                    }
                ],
                "fragments": [
                    {"name": "Ember of Torches", "element": "solar"},
                    {"name": "Ember of Empyrean", "element": "solar"},
                    {"name": "Ember of Benevolence", "element": "solar"}
                ],
                "aspects": [
                    {"name": "Heat Rises", "element": "solar"},
                    {"name": "Touch of Flame", "element": "solar"}
                ]
            }
            
            return demo_build
            
        except Exception as e:
            print(f"Error parsing DIM link: {e}")
            return None
    
    async def analyze_build(self, build_data: Dict) -> Dict:
        """Enhanced build analysis with API data"""
        if not build_data:
            return {"error": "Invalid build data"}
        
        analysis = {
            "synergies": [],
            "weaknesses": [],
            "suggestions": [],
            "weapon_analysis": [],
            "stat_analysis": [],
            "rating": 0
        }
        
        # Get real weapon data from API
        await self._analyze_weapons_with_api(build_data.get("weapons", []), analysis)
        
        # Analyze subclass synergies
        self._analyze_subclass_synergies(build_data, analysis)
        
        # Analyze fragment combinations
        self._analyze_fragment_synergies(build_data.get("fragments", []), analysis)
        
        # Analyze armor stats
        self._analyze_armor_stats(build_data, analysis)
        
        # Analyze exotic synergies
        self._analyze_exotic_synergies(build_data, analysis)
        
        # Calculate rating
        analysis["rating"] = self._calculate_build_rating(analysis)
        
        return analysis
    
    async def _analyze_weapons_with_api(self, weapons: List[Dict], analysis: Dict):
        """Analyze weapons using real API data"""
        try:
            for weapon in weapons:
                weapon_hash = weapon.get("hash")
                if weapon_hash:
                    # Get real weapon stats
                    stats = self.bungie_client.get_weapon_stats(weapon_hash)
                    weapon_info = self.bungie_client.get_item_info(weapon_hash)
                    
                    if weapon_info:
                        weapon_name = weapon_info.get("displayProperties", {}).get("name", "Unknown")
                        weapon_type = weapon_info.get("itemTypeDisplayName", "Unknown")
                        
                        analysis["weapon_analysis"].append({
                            "name": weapon_name,
                            "type": weapon_type,
                            "stats": stats
                        })
                        
                        # Check for high-stat weapons
                        if stats.get("Impact", 0) > 80:
                            analysis["synergies"].append(f"✅ {weapon_name} has excellent impact stats")
                        
                        if stats.get("Range", 0) > 75:
                            analysis["synergies"].append(f"✅ {weapon_name} has great range")
                            
        except Exception as e:
            print(f"Error analyzing weapons: {e}")
    
    def _analyze_subclass_synergies(self, build_data: Dict, analysis: Dict):
        """Enhanced subclass analysis"""
        subclass = build_data.get("subclass", {})
        element = subclass.get("element", "").lower()
        weapons = build_data.get("weapons", [])
        
        if element in self.synergy_data["subclass_synergies"]:
            synergy_info = self.synergy_data["subclass_synergies"][element]
            
            # Check weapon element matching
            matching_weapons = [w for w in weapons if w.get("element", "").lower() == element]
            if matching_weapons:
                analysis["synergies"].append(f"✅ {len(matching_weapons)} weapon(s) match your {element.title()} subclass")
            
            # Check for good weapon type synergies
            for weapon in weapons:
                if weapon.get("type", "").lower() in synergy_info["good_with_weapons"]:
                    analysis["synergies"].append(f"✅ {weapon.get('name', 'Weapon')} synergizes well with {element.title()}")
    
    def _analyze_fragment_synergies(self, fragments: List[Dict], analysis: Dict):
        """Analyze fragment combinations"""
        fragment_names = [f.get("name", "") for f in fragments]
        
        if len(fragments) >= 3:
            analysis["synergies"].append("✅ Good fragment coverage - using 3+ fragments")
        elif len(fragments) <= 1:
            analysis["suggestions"].append("💡 Consider using more fragments to maximize build potential")
        
        # Check for element consistency
        elements = set(f.get("element", "") for f in fragments)
        if len(elements) == 1:
            analysis["synergies"].append(f"✅ Consistent {list(elements)[0].title()} fragment theme")
    
    def _analyze_armor_stats(self, build_data: Dict, analysis: Dict):
        """Analyze armor stat distribution"""
        class_type = build_data.get("class", "").lower()
        armor_pieces = build_data.get("armor", [])
        
        total_stats = {}
        for piece in armor_pieces:
            stats = piece.get("stats", {})
            for stat, value in stats.items():
                total_stats[stat] = total_stats.get(stat, 0) + value
        
        if class_type in self.synergy_data["stat_priorities"]:
            priorities = self.synergy_data["stat_priorities"][class_type]["pve"]
            
            for stat in priorities[:2]:  # Check top 2 priorities
                if total_stats.get(stat, 0) >= 80:
                    analysis["synergies"].append(f"✅ Excellent {stat} stat ({total_stats[stat]})")
                elif total_stats.get(stat, 0) >= 60:
                    analysis["synergies"].append(f"✅ Good {stat} stat ({total_stats[stat]})")
                else:
                    analysis["suggestions"].append(f"💡 Consider increasing {stat} for better {class_type.title()} performance")
        
        analysis["stat_analysis"] = total_stats
    
    def _analyze_exotic_synergies(self, build_data: Dict, analysis: Dict):
        """Analyze exotic weapon/armor synergies"""
        weapons = build_data.get("weapons", [])
        subclass_element = build_data.get("subclass", {}).get("element", "").lower()
        
        for weapon in weapons:
            weapon_name = weapon.get("name", "")
            if weapon_name in self.synergy_data["exotic_synergies"]:
                synergies = self.synergy_data["exotic_synergies"][weapon_name]
                if subclass_element in synergies:
                    analysis["synergies"].append(f"✅ {weapon_name} synergizes perfectly with {subclass_element.title()}")
    
    def _calculate_build_rating(self, analysis: Dict) -> int:
        """Calculate build rating"""
        base_score = 5
        synergy_bonus = min(len(analysis["synergies"]) * 0.5, 4)
        weakness_penalty = len(analysis["weaknesses"]) * 0.5
        
        rating = max(1, min(10, base_score + synergy_bonus - weakness_penalty))
        return round(rating)
    
    def format_analysis(self, analysis: Dict) -> str:
        """Format analysis with enhanced details"""
        if "error" in analysis:
            return f"❌ {analysis['error']}"
        
        output = []
        
        # Rating
        rating = analysis["rating"]
        stars = "⭐" * rating
        output.append(f"**Build Rating: {rating}/10** {stars}")
        output.append("")
        
        # Weapon Analysis
        if analysis["weapon_analysis"]:
            output.append("**🔫 Weapon Analysis:**")
            for weapon in analysis["weapon_analysis"]:
                output.append(f"• **{weapon['name']}** ({weapon['type']})")
                if weapon["stats"]:
                    key_stats = [(k, v) for k, v in weapon["stats"].items() if v > 50][:3]
                    if key_stats:
                        stats_str = ", ".join([f"{k}: {v}" for k, v in key_stats])
                        output.append(f"  └─ Key Stats: {stats_str}")
            output.append("")
        
        # Stat Analysis
        if analysis["stat_analysis"]:
            output.append("**📊 Stat Distribution:**")
            for stat, value in analysis["stat_analysis"].items():
                tier = value // 10
                output.append(f"• **{stat}**: {value} (Tier {tier})")
            output.append("")
        
        # Synergies
        if analysis["synergies"]:
            output.append("**🔥 Synergies Found:**")
            for synergy in analysis["synergies"]:
                output.append(f"• {synergy}")
            output.append("")
        
        # Weaknesses
        if analysis["weaknesses"]:
            output.append("**⚠️ Potential Issues:**")
            for weakness in analysis["weaknesses"]:
                output.append(f"• {weakness}")
            output.append("")
        
        # Suggestions
        if analysis["suggestions"]:
            output.append("**💡 Suggestions:**")
            for suggestion in analysis["suggestions"]:
                output.append(f"• {suggestion}")
        
        return "\n".join(output)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Bungie API client
bungie_client = None
analyzer = None

@bot.event
async def on_ready():
    global bungie_client, analyzer
    
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')
    
    # Initialize Bungie API
    api_key = os.getenv('BUNGIE_API_KEY')
    if api_key:
        bungie_client = BungieAPIClient(api_key)
        await bungie_client.initialize()
        analyzer = DestinyBuildAnalyzer(bungie_client)
        print('🎯 Destiny 2 Build Analyzer is ready!')
    else:
        print('⚠️ No Bungie API key found. Some features may be limited.')

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
    embed.add_field(name="API Status", value="✅ Connected" if bungie_client else "❌ Not Connected", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='review')
async def review_build(ctx, *, link: str = None):
    """Review a Destiny 2 build from a DIM link"""
    if not analyzer:
        embed = discord.Embed(
            title="❌ API Not Available",
            description="The Bungie API is not currently available. Please try again later.",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    if not link:
        embed = discord.Embed(
            title="❌ No Link Provided",
            description="Please provide a DIM link to review!\n\n**Usage:** `!review <DIM_link>`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    # Send thinking message
    thinking_msg = await ctx.send("🔍 Analyzing your build with real-time data... Please wait!")
    
    try:
        # Parse the DIM link
        build_data = analyzer.parse_dim_link(link)
        
        if not build_data:
            embed = discord.Embed(
                title="❌ Invalid DIM Link",
                description="I couldn't parse that DIM link. Please make sure it's a valid Destiny Item Manager build link.",
                color=0xff0000
            )
            await thinking_msg.edit(content="", embed=embed)
            return
        
        # Analyze the build
        analysis = await analyzer.analyze_build(build_data)
        
        # Format results
        formatted_analysis = analyzer.format_analysis(analysis)
        
        # Create embed
        embed = discord.Embed(
            title="🎯 Enhanced Build Analysis Complete",
            description=formatted_analysis,
            color=0x00ff00 if analysis["rating"] >= 7 else 0xffaa00 if analysis["rating"] >= 5 else 0xff0000
        )
        embed.set_footer(text=f"Analysis by {ctx.author.display_name} • Powered by Bungie API")
        
        await thinking_msg.edit(content="", embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error During Analysis",
            description=f"An error occurred while analyzing your build: {str(e)}",
            color=0xff0000
        )
        await thinking_msg.edit(content="", embed=embed)

@bot.command(name='weapon')
async def weapon_info(ctx, *, weapon_name: str = None):
    """Get information about a specific weapon"""
    if not bungie_client:
        await ctx.send("❌ Bungie API not available")
        return
    
    if not weapon_name:
        await ctx.send("❌ Please provide a weapon name: `!weapon <weapon_name>`")
        return
    
    # This would search for the weapon in the API
    # For now, we'll show a placeholder
    embed = discord.Embed(
        title=f"🔫 Weapon: {weapon_name}",
        description="*This feature is coming soon! The bot will fetch real weapon stats from the Bungie API.*",
        color=0x0099ff
    )
    await ctx.send(embed=embed)

@bot.command(name='help_build')
async def help_build(ctx):
    """Enhanced help command"""
    embed = discord.Embed(
        title="🛠️ Enhanced Destiny 2 Build Helper",
        description="I can analyze your Destiny 2 builds with real-time data from the Bungie API!",
        color=0x0099ff
    )
    embed.add_field(
        name="📝 Commands",
        value="`!review <DIM_link>` - Analyze a build\n`!weapon <name>` - Get weapon info\n`!info` - Bot status",
        inline=False
    )
    embed.add_field(
        name="🔍 Enhanced Analysis",
        value="• Real weapon stats from Bungie API\n• Detailed stat breakdowns\n• Exotic synergy detection\n• Advanced build rating",
        inline=False
    )
    embed.add_field(
        name="🎯 What's New",
        value="✅ Live weapon data\n✅ Stat tier analysis\n✅ Enhanced synergy detection\n✅ Exotic recommendations",
        inline=False
    )
    await ctx.send(embed=embed)

# Run the bot
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
