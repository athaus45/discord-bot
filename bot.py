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

class DIMParser:
    """Parser for DIM (Destiny Item Manager) links"""

    def __init__(self, bungie_client: BungieAPIClient):
        self.bungie_client = bungie_client

    def parse_dim_link(self, url: str) -> Optional[Dict]:
        """Parse actual DIM link and extract loadout data"""
        try:
            # Check if it's a DIM link
            if "dim.gg" not in url and "destinyitemmanager.com" not in url:
                return None

            # Extract the loadout data from URL
            parsed_url = urlparse(url)

            # DIM links often have loadout data in URL fragments or query parameters
            # The exact format depends on DIM version, but typically it's base64 encoded

            # Try to extract from fragment (after #)
            fragment = parsed_url.fragment
            if fragment:
                try:
                    # Try to decode base64 data
                    decoded_data = self._decode_loadout_data(fragment)
                    if decoded_data:
                        return self._parse_loadout_data(decoded_data)
                except Exception as e:
                    print(f"❌ Error parsing fragment: {e}")

            # Try to extract from query parameters
            query_params = parse_qs(parsed_url.query)
            for key, values in query_params.items():
                if key.lower() in ['loadout', 'build', 'data']:
                    try:
                        decoded_data = self._decode_loadout_data(values[0])
                        if decoded_data:
                            return self._parse_loadout_data(decoded_data)
                    except Exception as e:
                        print(f"❌ Error parsing query param {key}: {e}")

            # If we can't parse the real link, return None
            print("⚠️ Could not parse DIM link format")
            return None

        except Exception as e:
            print(f"❌ Error parsing DIM link: {e}")
            return None

    def _decode_loadout_data(self, encoded_data: str) -> Optional[Dict]:
        """Decode base64 encoded loadout data"""
        try:
            # Remove URL encoding
            import urllib.parse
            decoded_url = urllib.parse.unquote(encoded_data)

            # Try base64 decoding
            try:
                decoded_bytes = base64.b64decode(decoded_url)
                # Try to decompress if it's gzipped
                try:
                    decompressed = gzip.decompress(decoded_bytes)
                    return json.loads(decompressed.decode('utf-8'))
                except:
                    # If not gzipped, try direct JSON parsing
                    return json.loads(decoded_bytes.decode('utf-8'))
            except:
                # If base64 fails, try direct JSON parsing
                return json.loads(decoded_url)

        except Exception as e:
            print(f"❌ Error decoding loadout data: {e}")
            return None

    def _parse_loadout_data(self, loadout_data: Dict) -> Dict:
        """Parse decoded loadout data into structured format"""
        try:
            parsed_build = {
                "class": "unknown",
                "subclass": {},
                "weapons": [],
                "armor": [],
                "fragments": [],
                "aspects": [],
                "mods": [],
                "stats": {}
            }

            # Extract class information
            if "characterClass" in loadout_data:
                class_map = {0: "titan", 1: "hunter", 2: "warlock"}
                parsed_build["class"] = class_map.get(loadout_data["characterClass"], "unknown")

            # Extract equipped items
            if "equipped" in loadout_data:
                equipped = loadout_data["equipped"]

                # Parse weapons
                weapon_slots = ["kinetic", "energy", "power"]
                for i, slot in enumerate(weapon_slots):
                    if i < len(equipped):
                        item_hash = equipped[i].get("hash")
                        if item_hash:
                            weapon_info = self._get_weapon_info(item_hash)
                            if weapon_info:
                                parsed_build["weapons"].append(weapon_info)

                # Parse armor (typically indices 3-7)
                armor_slots = ["helmet", "gauntlets", "chest", "legs", "class_item"]
                for i, slot in enumerate(armor_slots, 3):
                    if i < len(equipped):
                        item_hash = equipped[i].get("hash")
                        if item_hash:
                            armor_info = self._get_armor_info(item_hash)
                            if armor_info:
                                parsed_build["armor"].append(armor_info)

                # Parse subclass (usually last equipped item)
                subclass_item = equipped[-1] if equipped else None
                if subclass_item:
                    subclass_hash = subclass_item.get("hash")
                    if subclass_hash:
                        subclass_info = self._get_subclass_info(subclass_hash)
                        if subclass_info:
                            parsed_build["subclass"] = subclass_info

            return parsed_build

        except Exception as e:
            print(f"❌ Error parsing loadout data: {e}")
            return None

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

    def _get_armor_info(self, item_hash: str) -> Optional[Dict]:
        """Get armor information from hash"""
        try:
            item_info = self.bungie_client.get_item_info(item_hash)
            if not item_info:
                return None

            display_props = item_info.get("displayProperties", {})

            return {
                "hash": item_hash,
                "name": display_props.get("name", "Unknown"),
                "type": item_info.get("itemTypeDisplayName", "Unknown"),
                "is_exotic": self.bungie_client.is_exotic(item_hash),
                "stats": self._get_armor_stats(item_info)
            }
        except Exception as e:
            print(f"❌ Error getting armor info: {e}")
            return None

    def _get_subclass_info(self, item_hash: str) -> Dict:
        """Get subclass information from hash"""
        try:
            item_info = self.bungie_client.get_item_info(item_hash)
            if not item_info:
                return {}

            display_props = item_info.get("displayProperties", {})

            return {
                "hash": item_hash,
                "name": display_props.get("name", "Unknown"),
                "element": self._get_damage_type(item_info),
                "super": display_props.get("name", "Unknown")
            }
        except Exception as e:
            print(f"❌ Error getting subclass info: {e}")
            return {}

    def _get_damage_type(self, item_info: Dict) -> str:
        """Extract damage type from item info"""
        try:
            damage_type_hash = item_info.get("defaultDamageType", 0)
            return self.bungie_client.get_damage_type_name(damage_type_hash)
        except Exception as e:
            return "Unknown"

    def _get_armor_stats(self, item_info: Dict) -> Dict:
        """Extract armor stats from item info"""
        try:
            stats = {}
            if "stats" in item_info and "stats" in item_info["stats"]:
                for stat_hash, stat_value in item_info["stats"]["stats"].items():
                    stat_info = self.bungie_client.stat_definitions.get(stat_hash, {})
                    stat_name = stat_info.get("displayProperties", {}).get("name", "Unknown")
                    stats[stat_name] = stat_value.get("value", 0)
            return stats
        except Exception as e:
            return {}

class DestinyBuildAnalyzer:
    """Enhanced build analyzer with real API data"""

    def __init__(self, bungie_client: BungieAPIClient):
        self.bungie_client = bungie_client
        self.synergy_data = self._load_synergy_data()

    def _load_synergy_data(self) -> Dict:
        """Load comprehensive synergy data"""
        return {
            "subclass_synergies": {
                "solar": {
                    "keywords": ["burn", "ignite", "scorch", "radiant", "restoration", "solar"],
                    "synergistic_fragments": ["Ember of Torches", "Ember of Empyrean", "Ember of Benevolence"],
                    "good_with_weapons": ["fusion rifle", "linear fusion rifle", "hand cannon", "scout rifle"],
                    "exotic_synergies": ["Sunshot", "Polaris Lance", "Skyburner's Oath", "Prometheus Lens"]
                },
                "arc": {
                    "keywords": ["jolt", "blind", "amplified", "ionic trace", "arc"],
                    "synergistic_fragments": ["Spark of Shock", "Spark of Magnitude", "Spark of Ions"],
                    "good_with_weapons": ["smg", "sidearm", "pulse rifle", "trace rifle"],
                    "exotic_synergies": ["Riskrunner", "Trinity Ghoul", "Thunderlord", "Coldheart"]
                },
                "void": {
                    "keywords": ["volatile", "suppress", "weaken", "devour", "invisibility", "void"],
                    "synergistic_fragments": ["Echo of Starvation", "Echo of Harvest", "Echo of Undermining"],
                    "good_with_weapons": ["hand cannon", "sniper rifle", "bow", "glaive"],
                    "exotic_synergies": ["Thorn", "Le Monarque", "Graviton Lance", "Voidwalker"]
                },
                "stasis": {
                    "keywords": ["slow", "freeze", "shatter", "crystal", "stasis"],
                    "synergistic_fragments": ["Whisper of Chains", "Whisper of Shards", "Whisper of Bonds"],
                    "good_with_weapons": ["pulse rifle", "scout rifle", "linear fusion rifle"],
                    "exotic_synergies": ["Ager's Scepter", "Salvation's Grip", "Cryosthesia 77K"]
                },
                "strand": {
                    "keywords": ["suspend", "unraveling", "sever", "threadling", "strand"],
                    "synergistic_fragments": ["Thread of Ascent", "Thread of Fury", "Thread of Warding"],
                    "good_with_weapons": ["auto rifle", "machine gun", "glaive", "bow"],
                    "exotic_synergies": ["Osteo Striga", "Nezarec's Sin", "The Navigator"]
                }
            },
            "weapon_archetypes": {
                "high_impact": ["Better Devils", "Austringer", "Fatebringer"],
                "rapid_fire": ["Outbreak Perfected", "Bad Juju", "Graviton Lance"],
                "precision": ["Jade Rabbit", "Polaris Lance", "Skyburner's Oath"]
            },
            "stat_priorities": {
                "hunter": {
                    "pve": ["Recovery", "Discipline", "Mobility", "Intellect", "Resilience", "Strength"],
                    "pvp": ["Recovery", "Mobility", "Intellect", "Discipline", "Resilience", "Strength"]
                },
                "warlock": {
                    "pve": ["Recovery", "Discipline", "Intellect", "Resilience", "Mobility", "Strength"],
                    "pvp": ["Recovery", "Discipline", "Intellect", "Resilience", "Mobility", "Strength"]
                },
                "titan": {
                    "pve": ["Recovery", "Resilience", "Discipline", "Intellect", "Mobility", "Strength"],
                    "pvp": ["Recovery", "Resilience", "Strength", "Discipline", "Intellect", "Mobility"]
                }
            }
        }

    async def analyze_build(self, build_data: Dict) -> Dict:
        """Comprehensive build analysis with real API data"""
        if not build_data:
            return {"error": "Invalid build data"}

        analysis = {
            "synergies": [],
            "weaknesses": [],
            "suggestions": [],
            "weapon_analysis": [],
            "armor_analysis": [],
            "stat_analysis": {},
            "exotic_analysis": [],
            "element_distribution": {},
            "rating": 0
        }

        # Analyze each component
        await self._analyze_weapons(build_data.get("weapons", []), analysis)
        await self._analyze_armor(build_data.get("armor", []), analysis)
        await self._analyze_subclass_synergies(build_data, analysis)
        await self._analyze_element_distribution(build_data, analysis)
        await self._analyze_exotic_synergies(build_data, analysis)
        await self._analyze_stat_distribution(build_data, analysis)

        # Calculate overall rating
        analysis["rating"] = self._calculate_build_rating(analysis)

        return analysis

    async def _analyze_weapons(self, weapons: List[Dict], analysis: Dict):
        """Analyze weapon loadout with real data"""
        try:
            weapon_types = []
            elements = []

            for weapon in weapons:
                weapon_name = weapon.get("name", "Unknown")
                weapon_type = weapon.get("type", "Unknown")
                weapon_element = weapon.get("element", "Unknown")
                is_exotic = weapon.get("is_exotic", False)
                stats = weapon.get("stats", {})

                weapon_types.append(weapon_type.lower())
                elements.append(weapon_element.lower())

                # Add to weapon analysis
                weapon_analysis = {
                    "name": weapon_name,
                    "type": weapon_type,
                    "element": weapon_element,
                    "is_exotic": is_exotic,
                    "stats": stats,
                    "notable_stats": []
                }

                # Analyze notable stats
                if stats:
                    for stat_name, stat_value in stats.items():
                        if stat_value >= 80:
                            weapon_analysis["notable_stats"].append(f"Excellent {stat_name} ({stat_value})")
                            analysis["synergies"].append(f"✅ {weapon_name} has exceptional {stat_name} ({stat_value})")
                        elif stat_value >= 60:
                            weapon_analysis["notable_stats"].append(f"Good {stat_name} ({stat_value})")

                analysis["weapon_analysis"].append(weapon_analysis)

                # Check for exotic weapons
                if is_exotic:
                    analysis["exotic_analysis"].append({
                        "name": weapon_name,
                        "type": "weapon",
                        "element": weapon_element
                    })

            # Check weapon diversity
            unique_types = set(weapon_types)
            if len(unique_types) == 3:
                analysis["synergies"].append("✅ Good weapon diversity - different types for each slot")
            elif len(unique_types) == 1:
                analysis["weaknesses"].append("⚠️ All weapons are the same type - consider diversifying")

            # Check for multiple exotics (not allowed in game)
            exotic_count = sum(1 for w in weapons if w.get("is_exotic", False))
            if exotic_count > 1:
                analysis["weaknesses"].append("❌ Multiple exotic weapons detected - only one exotic weapon allowed")

        except Exception as e:
            print(f"❌ Error analyzing weapons: {e}")

    async def _analyze_armor(self, armor: List[Dict], analysis: Dict):
        """Analyze armor pieces with real data"""
        try:
            total_stats = {}
            exotic_armor = []

            for piece in armor:
                piece_name = piece.get("name", "Unknown")
                piece_type = piece.get("type", "Unknown")
                is_exotic = piece.get("is_exotic", False)
                stats = piece.get("stats", {})

                # Add to armor analysis
                analysis["armor_analysis"].append({
                    "name": piece_name,
                    "type": piece_type,
                    "is_exotic": is_exotic,
                    "stats": stats
                })

                # Accumulate stats
                for stat_name, stat_value in stats.items():
                    total_stats[stat_name] = total_stats.get(stat_name, 0) + stat_value

                # Check for exotic armor
                if is_exotic:
                    exotic_armor.append(piece_name)
                    analysis["exotic_analysis"].append({
                        "name": piece_name,
                        "type": "armor",
                        "slot": piece_type
                    })

            # Check for multiple exotic armor pieces
            if len(exotic_armor) > 1:
                analysis["weaknesses"].append("❌ Multiple exotic armor pieces detected - only one exotic armor allowed")
            elif len(exotic_armor) == 1:
                analysis["synergies"].append(f"✅ Using exotic armor: {exotic_armor[0]}")

            analysis["stat_analysis"] = total_stats

        except Exception as e:
            print(f"❌ Error analyzing armor: {e}")

    async def _analyze_subclass_synergies(self, build_data: Dict, analysis: Dict):
        """Analyze subclass synergies with weapons and armor"""
        try:
            subclass = build_data.get("subclass", {})
            subclass_element = subclass.get("element", "").lower()
            weapons = build_data.get("weapons", [])

            if subclass_element and subclass_element in self.synergy_data["subclass_synergies"]:
                synergy_info = self.synergy_data["subclass_synergies"][subclass_element]

                # Check weapon element matching
                matching_weapons = [w for w in weapons if w.get("element", "").lower() == subclass_element]
                if matching_weapons:
                    analysis["synergies"].append(f"✅ {len(matching_weapons)} weapon(s) match your {subclass_element.title()} subclass")

                # Check weapon type synergies
                for weapon in weapons:
                    weapon_type = weapon.get("type", "").lower()
                    if any(wt in weapon_type for wt in synergy_info["good_with_weapons"]):
                        analysis["synergies"].append(f"✅ {weapon.get('name', 'Weapon')} ({weapon_type}) synergizes well with {subclass_element.title()}")

                # Check exotic weapon synergies
                for weapon in weapons:
                    if weapon.get("is_exotic", False):
                        weapon_name = weapon.get("name", "")
                        if weapon_name in synergy_info["exotic_synergies"]:
                            analysis["synergies"].append(f"🔥 {weapon_name} has perfect synergy with {subclass_element.title()}!")

        except Exception as e:
            print(f"❌ Error analyzing subclass synergies: {e}")

    async def _analyze_element_distribution(self, build_data: Dict, analysis: Dict):
        """Analyze elemental distribution across weapons"""
        try:
            weapons = build_data.get("weapons", [])
            elements = [w.get("element", "").lower() for w in weapons if w.get("element")]

            element_count = {}
            for element in elements:
                element_count[element] = element_count.get(element, 0) + 1

            analysis["element_distribution"] = element_count

            # Check for elemental coverage
            if len(element_count) == 3:
                analysis["synergies"].append("✅ Excellent elemental coverage - all three weapon elements covered")
            elif len(element_count) == 1:
                single_element = list(element_count.keys())[0]
                analysis["suggestions"].append(f"💡 Consider adding weapons of different elements for better coverage (currently all {single_element.title()})")

        except Exception as e:
            print(f"❌ Error analyzing element distribution: {e}")

    async def _analyze_exotic_synergies(self, build_data: Dict, analysis: Dict):
        """Analyze exotic weapon and armor synergies"""
        try:
            weapons = build_data.get("weapons", [])
            armor = build_data.get("armor", [])
            subclass_element = build_data.get("subclass", {}).get("element", "").lower()

            exotic_weapons = [w for w in weapons if w.get("is_exotic", False)]
            exotic_armor = [a for a in armor if a.get("is_exotic", False)]

            # Check if exotic choices complement each other
            if exotic_weapons and exotic_armor:
                weapon_name = exotic_weapons[0].get("name", "")
                armor_name = exotic_armor[0].get("name", "")
                analysis["synergies"].append(f"✅ Using exotic weapon and armor: {weapon_name} + {armor_name}")

            # Check for element matching with subclass
            for weapon in exotic_weapons:
                weapon_element = weapon.get("element", "").lower()
                if weapon_element == subclass_element:
                    analysis["synergies"].append(f"🔥 {weapon.get('name', 'Exotic weapon')} element matches your subclass!")

        except Exception as e:
            print(f"❌ Error analyzing exotic synergies: {e}")

    async def _analyze_stat_distribution(self, build_data: Dict, analysis: Dict):
        """Analyze stat distribution for the class"""
        try:
            class_type = build_data.get("class", "").lower()
            total_stats = analysis.get("stat_analysis", {})

            if class_type in self.synergy_data["stat_priorities"]:
                priorities = self.synergy_data["stat_priorities"][class_type]["pve"]

                # Check top priority stats
                for i, stat in enumerate(priorities[:3]):  # Top 3 priorities
                    stat_value = total_stats.get(stat, 0)
                    stat_tier = stat_value // 10

                    if stat_tier >= 10:
                        analysis["synergies"].append(f"🔥 Maxed {stat} (T{stat_tier}) - perfect for {class_type.title()}!")
                    elif stat_tier >= 8:
                        analysis["synergies"].append(f"✅ Excellent {stat} (T{stat_tier}) - great for {class_type.title()}")
                    elif stat_tier >= 6:
                        analysis["synergies"].append(f"✅ Good {stat} (T{stat_tier}) - solid for {class_type.title()}")
                    elif i == 0:  # Most important stat
                        analysis["suggestions"].append(f"💡 Consider increasing {stat} (currently T{stat_tier}) - it's crucial for {class_type.title()}")

                # Check for balanced builds
                high_tier_stats = [stat for stat, value in total_stats.items() if value >= 60]
                if len(high_tier_stats) >= 4:
                    analysis["synergies"].append("✅ Well-balanced stat distribution - multiple high-tier stats")

        except Exception as e:
            print(f"❌ Error analyzing stat distribution: {e}")

    def _calculate_build_rating(self, analysis: Dict) -> int:
        """Calculate comprehensive build rating"""
        base_score = 5.0

        # Positive factors
        synergy_bonus = min(len(analysis["synergies"]) * 0.3, 3.0)
        exotic_bonus = 0.5 if analysis["exotic_analysis"] else 0
        stat_bonus = 0.5 if len([s for s in analysis["stat_analysis"].values() if s >= 60]) >= 3 else 0

        # Negative factors
        weakness_penalty = len(analysis["weaknesses"]) * 0.8

        # Calculate final rating
        rating = base_score + synergy_bonus + exotic_bonus + stat_bonus - weakness_penalty
        return max(1, min(10, round(rating)))

    def format_analysis(self, analysis: Dict) -> str:
        """Format comprehensive analysis"""
        if "error" in analysis:
            return f"❌ {analysis['error']}"

        output = []

        # Rating header
        rating = analysis["rating"]
        stars = "⭐" * rating
        rating_desc = "Excellent" if rating >= 8 else "Good" if rating >= 6 else "Needs Work" if rating >= 4 else "Poor"
        output.append(f"**🎯 Build Rating: {rating}/10** {stars}")
        output.append(f"*{rating_desc} Build*")
        output.append("")

        # Weapon Analysis
        if analysis["weapon_analysis"]:
            output.append("**🔫 Weapon Loadout:**")
            for weapon in analysis["weapon_analysis"]:
                exotic_marker = "🌟" if weapon["is_exotic"] else ""
                output.append(f"• {exotic_marker}**{weapon['name']}** ({weapon['type']})")
                output.append(f"  └─ Element: {weapon['element'].title()}")

                if weapon["notable_stats"]:
                    output.append(f"  └─ {', '.join(weapon['notable_stats'])}")
            output.append("")

        # Armor Analysis
        if analysis["armor_analysis"]:
            output.append("**🛡️ Armor Setup:**")
            for armor in analysis["armor_analysis"]:
                exotic_marker = "🌟" if armor["is_exotic"] else ""
                output.append(f"• {exotic_marker}**{armor['name']}** ({armor['type']})")
            output.append("")

        # Stat Distribution
        if analysis["stat_analysis"]:
            output.append("**📊 Stat Distribution:**")
            for stat, value in analysis["stat_analysis"].items():
                tier = value // 10
                tier_display = f"T{tier}" if tier <= 10 else f"T10+"
                bar_length = min(tier, 10)
                bar = "█" * bar_length + "░" * (10 - bar_length)
                output.append(f"• **{stat}**: {value} ({tier_display}) {bar}")
            output.append("")

        # Element Distribution
        if analysis["element_distribution"]:
            output.append("**⚡ Elemental Coverage:**")
            for element, count in analysis["element_distribution"].items():
                output.append(f"• {element.title()}: {count} weapon(s)")
            output.append("")

        # Exotic Analysis
        if analysis["exotic_analysis"]:
            output.append("**🌟 Exotic Gear:**")
            for exotic in analysis["exotic_analysis"]:
                output.append(f"• {exotic['name']} ({exotic['type'].title()})")
            output.append("")

        # Synergies
        if analysis["synergies"]:
            output.append("**🔥 Build Synergies:**")
            for synergy in analysis["synergies"]:
                output.append(f"• {synergy}")
            output.append("")

        # Weaknesses
        if analysis["weaknesses"]:
            output.append("**⚠️ Issues Found:**")
            for weakness in analysis["weaknesses"]:
                output.append(f"• {weakness}")
            output.append("")

        # Suggestions
        if analysis["suggestions"]:
            output.append("**💡 Improvement Suggestions:**")
            for suggestion in analysis["suggestions"]:
                output.append(f"• {suggestion}")

        return "\n".join(output)

# Enhanced Bot Commands
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
bungie_client = None
dim_parser = None
analyzer = None

@bot.event
async def on_ready():
    global bungie_client, dim_parser, analyzer

    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} servers')

    # Initialize Bungie API
    api_key = os.getenv('BUNGIE_API_KEY')
    if api_key:
        bungie_client = BungieAPIClient(api_key)
        success = await bungie_client.initialize()

        if success:
            dim_parser = DIMParser(bungie_client)
            analyzer = DestinyBuildAnalyzer(bungie_client)
            print('🎯 Enhanced Destiny 2 Build Analyzer is ready!')
            print('✅ Real DIM link parsing enabled')
            print('✅ Live weapon/armor data integration active')
        else:
            print('❌ Failed to initialize Bungie API - some features disabled')
    else:
        print('⚠️ No Bungie API key found. Bot will run with limited functionality.')

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

@bot.command(name='review')
async def review_build(ctx, *, link: str = None):
    """Review a Destiny 2 build from a real DIM link"""
    if not analyzer or not dim_parser:
        embed = discord.Embed(
            title="❌ Service Unavailable",
            description="The build analysis service is not available. Please try again later.",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return

    if not link:
        embed = discord.Embed(
            title="❌ No Link Provided",
            description="Please provide a DIM link to analyze!\n\n**Usage:** `!review <DIM_link>`\n\n**Example:** `!review https://dim.gg/your-build-link`",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return

    # Send analysis message
    thinking_msg = await ctx.send("🔍 **Analyzing your build...**\n• Parsing DIM link data\n• Fetching weapon stats from Bungie API\n• Analyzing synergies and balance\n\n*This may take a moment...*")

    try:
        # Parse the real DIM link
        build_data = dim_parser.parse_dim_link(link)

        if not build_data:
            embed = discord.Embed(
                title="❌ Unable to Parse DIM Link",
                description="I couldn't extract build data from that link. Please ensure:\n\n• The link is from dim.gg or destinyitemmanager.com\n• The link contains valid loadout data\n• The link is properly formatted\n\n**Note:** Some DIM link formats may not be supported yet.",
                color=0xff0000
            )
            await thinking_msg.edit(content="", embed=embed)
            return

        # Analyze the build with real data
        analysis = await analyzer.analyze_build(build_data)

        # Format the comprehensive analysis
        formatted_analysis = analyzer.format_analysis(analysis)

        # Determine embed color based on rating
        rating = analysis["rating"]
        embed_color = 0x00ff00 if rating >= 8 else 0xffaa00 if rating >= 6 else 0xff6600 if rating >= 4 else 0xff0000

        # Create detailed embed
        embed = discord.Embed(
            title="🎯 Comprehensive Build Analysis",
            description=formatted_analysis,
            color=embed_color
        )

        # Add footer with metadata
        class_name = build_data.get("class", "Unknown").title()
        subclass_name = build_data.get("subclass", {}).get("name", "Unknown")
        embed.set_footer(text=f"Analysis for {ctx.author.display_name} • {class_name} • {subclass_name} • Powered by Bungie API")

        await thinking_msg.edit(content="", embed=embed)

    except Exception as e:
        embed = discord.Embed(
            title="❌ Analysis Error",
            description=f"An error occurred while analyzing your build:\n```{str(e)}```\n\nPlease try again or contact support if the issue persists.",
            color=0xff0000
        )
        await thinking_msg.edit(content="", embed=embed)
        print(f"❌ Build analysis error: {e}")

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
