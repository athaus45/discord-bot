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

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class DestinyBuildAnalyzer:
    """Main class for analyzing Destiny 2 builds from DIM links"""
    
    def __init__(self):
        # Destiny 2 API endpoints
        self.bungie_api_base = "https://www.bungie.net/Platform"
        self.manifest_url = f"{self.bungie_api_base}/Destiny2/Manifest/"
        
        # Build synergy data - this would ideally come from a database
        self.synergy_data = self._load_synergy_data()
        
    def _load_synergy_data(self) -> Dict:
        """Load synergy data for build analysis"""
        return {
            "subclass_synergies": {
                "solar": {
                    "keywords": ["burn", "ignite", "scorch", "radiant", "restoration"],
                    "synergistic_mods": ["elemental charge", "well of radiance", "solar siphon"],
                    "weapon_types": ["fusion rifle", "linear fusion rifle", "solar weapons"]
                },
                "arc": {
                    "keywords": ["jolt", "blind", "amplified", "ionic trace"],
                    "synergistic_mods": ["arc siphon", "elemental charge", "font of might"],
                    "weapon_types": ["smg", "sidearm", "arc weapons"]
                },
                "void": {
                    "keywords": ["volatile", "suppress", "weaken", "devour", "invisibility"],
                    "synergistic_mods": ["void siphon", "elemental charge", "font of might"],
                    "weapon_types": ["hand cannon", "sniper rifle", "void weapons"]
                },
                "stasis": {
                    "keywords": ["slow", "freeze", "shatter", "crystal"],
                    "synergistic_mods": ["stasis siphon", "elemental charge"],
                    "weapon_types": ["pulse rifle", "scout rifle", "stasis weapons"]
                },
                "strand": {
                    "keywords": ["suspend", "unraveling", "sever", "threadling"],
                    "synergistic_mods": ["strand siphon", "elemental charge"],
                    "weapon_types": ["auto rifle", "machine gun", "strand weapons"]
                }
            },
            "fragment_synergies": {
                # This would be populated with actual fragment data
                "common_combos": [
                    ["Spark of Feedback", "Spark of Resistance"],
                    ["Whisper of Chains", "Whisper of Shards"],
                    ["Echo of Starvation", "Echo of Harvest"]
                ]
            },
            "armor_mod_synergies": {
                "cwl_builds": ["taking charge", "high energy fire", "elemental charge"],
                "well_builds": ["well of life", "bountiful wells", "font of might"],
                "warmind_builds": ["warmind's protection", "global reach", "burning cells"]
            }
        }
    
    def parse_dim_link(self, url: str) -> Optional[Dict]:
        """Parse a DIM link to extract build information"""
        try:
            # DIM links typically contain base64 encoded build data
            parsed_url = urlparse(url)
            
            # Check if it's a valid DIM link
            if "destinyitemmanager.com" not in parsed_url.netloc:
                return None
            
            # Extract the build data from the URL
            # DIM links often have the format: https://destinyitemmanager.com/...?loadout=<encoded_data>
            query_params = parse_qs(parsed_url.query)
            
            if 'loadout' in query_params:
                encoded_data = query_params['loadout'][0]
                try:
                    # Decode the base64 data
                    decoded_data = base64.b64decode(encoded_data + '==')  # Add padding if needed
                    build_data = json.loads(decoded_data.decode('utf-8'))
                    return build_data
                except Exception as e:
                    print(f"Error decoding build data: {e}")
                    return None
            
            return None
            
        except Exception as e:
            print(f"Error parsing DIM link: {e}")
            return None
    
    def analyze_build(self, build_data: Dict) -> Dict:
        """Analyze a build and provide feedback"""
        if not build_data:
            return {"error": "Invalid build data"}
        
        analysis = {
            "synergies": [],
            "weaknesses": [],
            "suggestions": [],
            "rating": 0
        }
        
        # Extract key components
        subclass = build_data.get("subclass", {})
        weapons = build_data.get("weapons", [])
        armor = build_data.get("armor", [])
        fragments = build_data.get("fragments", [])
        aspects = build_data.get("aspects", [])
        
        # Analyze subclass synergies
        self._analyze_subclass_synergies(subclass, weapons, armor, analysis)
        
        # Analyze fragment combinations
        self._analyze_fragment_synergies(fragments, analysis)
        
        # Analyze armor mods
        self._analyze_armor_mods(armor, analysis)
        
        # Analyze weapon synergies
        self._analyze_weapon_synergies(weapons, subclass, analysis)
        
        # Calculate overall rating
        analysis["rating"] = self._calculate_build_rating(analysis)
        
        return analysis
    
    def _analyze_subclass_synergies(self, subclass: Dict, weapons: List, armor: List, analysis: Dict):
        """Analyze subclass synergies"""
        subclass_element = subclass.get("element", "").lower()
        
        if subclass_element in self.synergy_data["subclass_synergies"]:
            synergy_info = self.synergy_data["subclass_synergies"][subclass_element]
            
            # Check weapon synergies
            for weapon in weapons:
                weapon_element = weapon.get("element", "").lower()
                weapon_type = weapon.get("type", "").lower()
                
                if weapon_element == subclass_element:
                    analysis["synergies"].append(f"✅ {weapon_element.title()} weapon matches subclass element")
                
                if weapon_type in synergy_info["weapon_types"]:
                    analysis["synergies"].append(f"✅ {weapon_type.title()} synergizes well with {subclass_element.title()}")
    
    def _analyze_fragment_synergies(self, fragments: List, analysis: Dict):
        """Analyze fragment combinations"""
        fragment_names = [f.get("name", "") for f in fragments]
        
        # Check for known synergistic combinations
        for combo in self.synergy_data["fragment_synergies"]["common_combos"]:
            if all(fragment in fragment_names for fragment in combo):
                analysis["synergies"].append(f"✅ Excellent fragment combo: {' + '.join(combo)}")
        
        # Check for anti-synergies or redundancies
        if len(fragments) < 2:
            analysis["suggestions"].append("💡 Consider adding more fragments to maximize build potential")
    
    def _analyze_armor_mods(self, armor: List, analysis: Dict):
        """Analyze armor mod synergies"""
        all_mods = []
        for armor_piece in armor:
            mods = armor_piece.get("mods", [])
            all_mods.extend([mod.get("name", "").lower() for mod in mods])
        
        # Check for build archetypes
        cwl_mods = [mod for mod in all_mods if any(cwl in mod for cwl in self.synergy_data["armor_mod_synergies"]["cwl_builds"])]
        well_mods = [mod for mod in all_mods if any(well in mod for well in self.synergy_data["armor_mod_synergies"]["well_builds"])]
        
        if len(cwl_mods) >= 2:
            analysis["synergies"].append("✅ Strong Charged with Light build detected")
        elif len(cwl_mods) == 1:
            analysis["suggestions"].append("💡 Consider adding more CWL mods for better synergy")
        
        if len(well_mods) >= 2:
            analysis["synergies"].append("✅ Elemental Well build detected")
        elif len(well_mods) == 1:
            analysis["suggestions"].append("💡 Consider adding more Well mods for better synergy")
    
    def _analyze_weapon_synergies(self, weapons: List, subclass: Dict, analysis: Dict):
        """Analyze weapon loadout synergies"""
        weapon_types = [w.get("type", "") for w in weapons]
        weapon_elements = [w.get("element", "") for w in weapons]
        
        # Check for element diversity
        unique_elements = set(weapon_elements)
        if len(unique_elements) >= 2:
            analysis["synergies"].append("✅ Good elemental diversity in weapon loadout")
        
        # Check for range coverage
        ranges = {"short": 0, "medium": 0, "long": 0}
        for weapon_type in weapon_types:
            if weapon_type.lower() in ["sidearm", "smg", "shotgun"]:
                ranges["short"] += 1
            elif weapon_type.lower() in ["auto rifle", "pulse rifle", "hand cannon"]:
                ranges["medium"] += 1
            elif weapon_type.lower() in ["scout rifle", "sniper rifle", "linear fusion rifle"]:
                ranges["long"] += 1
        
        if all(count > 0 for count in ranges.values()):
            analysis["synergies"].append("✅ Excellent range coverage across all weapon slots")
        elif sum(count > 0 for count in ranges.values()) >= 2:
            analysis["synergies"].append("✅ Good range coverage")
        else:
            analysis["suggestions"].append("💡 Consider weapons that cover different engagement ranges")
    
    def _calculate_build_rating(self, analysis: Dict) -> int:
        """Calculate an overall build rating out of 10"""
        synergy_score = min(len(analysis["synergies"]) * 2, 7)  # Max 7 points from synergies
        weakness_penalty = len(analysis["weaknesses"]) * 1  # 1 point penalty per weakness
        
        rating = max(1, min(10, synergy_score - weakness_penalty + 3))  # Base 3 points
        return rating
    
    def format_analysis(self, analysis: Dict) -> str:
        """Format the analysis into a readable string"""
        if "error" in analysis:
            return f"❌ {analysis['error']}"
        
        output = []
        
        # Rating
        rating = analysis["rating"]
        stars = "⭐" * rating
        output.append(f"**Build Rating: {rating}/10** {stars}")
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
            output.append("**💡 Suggestions for Improvement:**")
            for suggestion in analysis["suggestions"]:
                output.append(f"• {suggestion}")
            output.append("")
        
        return "\n".join(output)

# Initialize the analyzer
analyzer = DestinyBuildAnalyzer()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')
    print('Destiny 2 Build Analyzer is ready!')

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
    embed.add_field(name="Commands", value="!hello, !ping, !info, !review", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='review')
async def review_build(ctx, *, link: str = None):
    """Review a Destiny 2 build from a DIM link"""
    if not link:
        embed = discord.Embed(
            title="❌ No Link Provided",
            description="Please provide a DIM link to review!\n\n**Usage:** `!review <DIM_link>`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    # Send a "thinking" message
    thinking_msg = await ctx.send("🔍 Analyzing your build... Please wait!")
    
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
        analysis = analyzer.analyze_build(build_data)
        
        # Format the results
        formatted_analysis = analyzer.format_analysis(analysis)
        
        # Create embed
        embed = discord.Embed(
            title="🎯 Build Analysis Complete",
            description=formatted_analysis,
            color=0x00ff00 if analysis["rating"] >= 7 else 0xffaa00 if analysis["rating"] >= 5 else 0xff0000
        )
        embed.set_footer(text=f"Analysis requested by {ctx.author.display_name}")
        
        await thinking_msg.edit(content="", embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Error During Analysis",
            description=f"An error occurred while analyzing your build: {str(e)}",
            color=0xff0000
        )
        await thinking_msg.edit(content="", embed=embed)

@bot.command(name='help_build')
async def help_build(ctx):
    """Show help for build analysis commands"""
    embed = discord.Embed(
        title="🛠️ Destiny 2 Build Helper",
        description="I can help you analyze your Destiny 2 builds!",
        color=0x0099ff
    )
    embed.add_field(
        name="📝 Commands",
        value="`!review <DIM_link>` - Analyze a build from a DIM link",
        inline=False
    )
    embed.add_field(
        name="🔗 How to get a DIM link",
        value="1. Go to [Destiny Item Manager](https://destinyitemmanager.com)\n2. Create your build\n3. Click the share button\n4. Copy the link and use it with `!review`",
        inline=False
    )
    embed.add_field(
        name="🎯 What I analyze",
        value="• Subclass synergies\n• Fragment combinations\n• Armor mod synergies\n• Weapon loadout balance\n• Overall build rating",
        inline=False
    )
    await ctx.send(embed=embed)

# Run the bot
if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
