import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional
from config import GUILD_ID, BOT_SETTINGS

logger = logging.getLogger(__name__)

class EarthquakeSettingsView(discord.ui.View):
    """View for managing earthquake feed settings"""
    
    def __init__(self, cog: 'EarthquakeFeed'):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label="Setup Channel", style=discord.ButtonStyle.primary, custom_id="earthquake_setup")
    async def setup_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Setup the channel for earthquake alerts"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        # Create channel selector
        select = discord.ui.ChannelSelect(
            placeholder="Select a channel for earthquake alerts",
            channel_types=[discord.ChannelType.text],
            custom_id="earthquake_channel"
        )
        
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Please select a channel for earthquake alerts:", view=view, ephemeral=True)
        
    @discord.ui.button(label="Toggle Feed", style=discord.ButtonStyle.secondary, custom_id="earthquake_toggle")
    async def toggle_feed(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle the earthquake feed on/off"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild_id)
        if guild_id in self.cog.feed_channels:
            # Toggle the enabled state
            self.cog.feed_channels[guild_id]['enabled'] = not self.cog.feed_channels[guild_id]['enabled']
            await self.cog.save_settings()
            
            status = "enabled" if self.cog.feed_channels[guild_id]['enabled'] else "disabled"
            await interaction.response.send_message(f"Earthquake feed has been {status}.", ephemeral=True)
        else:
            await interaction.response.send_message("Please set up a channel first using the Setup Channel button.", ephemeral=True)
            
    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, custom_id="earthquake_status")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check the status of the earthquake feed"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild_id)
        if guild_id in self.cog.feed_channels:
            channel = self.cog.bot.get_channel(self.cog.feed_channels[guild_id]['channel_id'])
            enabled = self.cog.feed_channels[guild_id]['enabled']
            last_time = self.cog.feed_channels[guild_id]['last_quake_time']
            current_color = self.cog.feed_channels[guild_id].get('embed_color', 0xFF0000)
            mention_roles = self.cog.feed_channels[guild_id].get('mention_roles', [])
            
            status = "Enabled" if enabled else "Disabled"
            color = 0x00FF00 if enabled else 0xFF0000
            
            embed = discord.Embed(
                title="Earthquake Feed Status",
                color=color
            )
            embed.add_field(name="Channel", value=channel.mention if channel else "Unknown", inline=False)
            embed.add_field(name="Status", value=status, inline=False)
            embed.add_field(name="Current Color", value=f"#{current_color:06X}", inline=False)
            embed.add_field(name="Last Earthquake", value=last_time.strftime("%Y-%m-%d %H:%M:%S UTC") if last_time else "None", inline=False)
            
            # Add mention roles to status
            if mention_roles:
                roles = [f"<@&{role_id}>" for role_id in mention_roles]
                embed.add_field(name="Mention Roles", value="\n".join(roles), inline=False)
            else:
                embed.add_field(name="Mention Roles", value="None", inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("Earthquake feed is not set up. Use the Setup Channel button to configure it.", ephemeral=True)

    @discord.ui.button(label="Color Settings", style=discord.ButtonStyle.secondary, custom_id="earthquake_color")
    async def color_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open color settings for earthquake embeds"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        # Show the color input modal
        modal = ColorInputModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Manage Roles", style=discord.ButtonStyle.secondary, custom_id="earthquake_roles")
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Manage roles to mention for earthquake alerts"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        guild_id = str(interaction.guild_id)
        if guild_id not in self.cog.feed_channels:
            await interaction.response.send_message("Please set up a channel first using the Setup Channel button.", ephemeral=True)
            return
            
        # Create role selector
        select = discord.ui.RoleSelect(
            placeholder="Select roles to mention",
            custom_id="earthquake_roles",
            min_values=0,
            max_values=5
        )
        
        # Get current roles
        current_roles = self.cog.feed_channels[guild_id].get('mention_roles', [])
        if current_roles:
            select.default_values = [interaction.guild.get_role(role_id) for role_id in current_roles if interaction.guild.get_role(role_id)]
        
        async def role_select_callback(interaction: discord.Interaction):
            try:
                selected_roles = [role.id for role in select.values]
                guild_id = str(interaction.guild_id)
                
                if guild_id in self.cog.feed_channels:
                    # Update mention roles
                    self.cog.feed_channels[guild_id]['mention_roles'] = selected_roles
                    await self.cog.save_settings()
                    
                    # Create response message
                    if selected_roles:
                        role_mentions = [f"<@&{role}>" for role in selected_roles]
                        message = f"Updated mention roles to:\n" + "\n".join(role_mentions)
                    else:
                        message = "Removed all mention roles."
                        
                    await interaction.response.send_message(message, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "Please set up a channel first using the Setup Channel button.",
                        ephemeral=True
                    )
                    
            except Exception as e:
                logger.error(f"Error updating mention roles: {e}")
                await interaction.response.send_message(
                    "An error occurred while updating mention roles.",
                    ephemeral=True
                )
        
        select.callback = role_select_callback
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message("Select roles to mention for earthquake alerts:", view=view, ephemeral=True)

class ColorInputModal(discord.ui.Modal, title="Set Embed Color"):
    def __init__(self, cog: 'EarthquakeFeed'):
        super().__init__()
        self.cog = cog
        
        self.color_input = discord.ui.TextInput(
            label="Enter Hex Color (e.g., #FF0000)",
            placeholder="#FF0000",
            min_length=7,
            max_length=7,
            required=True
        )
        self.add_item(self.color_input)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Remove # if present and convert to integer
            hex_color = self.color_input.value.lstrip('#')
            color_value = int(hex_color, 16)
            
            guild_id = str(interaction.guild_id)
            if guild_id in self.cog.feed_channels:
                # Store the color as an integer
                self.cog.feed_channels[guild_id]['embed_color'] = color_value
                await self.cog.save_settings()
                
                # Show a preview of the color
                preview_embed = discord.Embed(
                    title="Color Preview",
                    description=f"New color set to #{hex_color.upper()}",
                    color=color_value
                )
                await interaction.response.send_message(embed=preview_embed, ephemeral=True)
            else:
                await interaction.response.send_message("Please set up a channel first using the Setup Channel button.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Invalid hex color format. Please use format like #FF0000.", ephemeral=True)

class EarthquakeFeed(commands.Cog):
    """Cog for monitoring and posting earthquake feeds"""
    
    def __init__(self, bot):
        self.bot = bot
        self.feed_channels = {}
        self.last_quake_id = None
        self.last_quake_time = None
        self.session = None
        self.feed_task = None
        self.embed_color = int(BOT_SETTINGS["embed_color"], 16)
        self.settings_file = "data/earthquake_settings.json"
        # Significant earthquakes feed (M3.5+ globally) with 24-hour history
        self.feed_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
        
    async def cog_load(self):
        """Load settings and start the feed task when the cog is loaded"""
        self.load_settings()
        self.session = aiohttp.ClientSession()
        self.feed_task = asyncio.create_task(self.earthquake_feed_loop())
        logger.info("Earthquake feed cog loaded")
        
    async def cog_unload(self):
        """Clean up when the cog is unloaded"""
        if self.feed_task:
            self.feed_task.cancel()
        if self.session:
            await self.session.close()
        logger.info("Earthquake feed cog unloaded")

    def load_settings(self):
        """Load settings from the JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    self.feed_channels = {
                        str(guild_id): {
                            'channel_id': channel_data['channel_id'],
                            'last_quake_time': datetime.fromisoformat(channel_data['last_quake_time']) if channel_data.get('last_quake_time') else None,
                            'enabled': channel_data.get('enabled', True),
                            'embed_color': channel_data.get('embed_color', 0xFF0000),
                            'mention_roles': channel_data.get('mention_roles', [])
                        }
                        for guild_id, channel_data in data.get('feed_channels', {}).items()
                    }
                    self.last_quake_id = data.get('last_earthquake', {}).get('id')
                    self.last_quake_time = datetime.fromisoformat(data['last_earthquake']['time']) if data.get('last_earthquake', {}).get('time') else None
            else:
                self.feed_channels = {}
                self.last_quake_id = None
                self.last_quake_time = None
        except Exception as e:
            logger.error(f"Error loading earthquake settings: {e}")
            self.feed_channels = {}
            self.last_quake_id = None
            self.last_quake_time = None

    async def save_settings(self):
        """Save settings to the JSON file"""
        try:
            data = {
                'feed_channels': {
                    guild_id: {
                        'channel_id': channel_data['channel_id'],
                        'last_quake_time': channel_data['last_quake_time'].isoformat() if channel_data.get('last_quake_time') else None,
                        'enabled': channel_data.get('enabled', True),
                        'embed_color': channel_data.get('embed_color', 0xFF0000),
                        'mention_roles': channel_data.get('mention_roles', [])
                    }
                    for guild_id, channel_data in self.feed_channels.items()
                },
                'last_earthquake': {
                    'id': self.last_quake_id,
                    'time': self.last_quake_time.isoformat() if self.last_quake_time else None
                }
            }
            
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving earthquake settings: {e}")

    async def earthquake_feed_loop(self):
        """Background task to check for new earthquakes"""
        await self.bot.wait_until_ready()
        
        # Post only the most recent earthquake when the bot starts
        await self.check_most_recent_earthquake()
        
        while not self.bot.is_closed():
            try:
                await self.check_earthquakes()
                # Check every 5 minutes
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in earthquake feed loop: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying if there's an error

    async def check_most_recent_earthquake(self):
        """Check and post only the most recent earthquake on startup"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.feed_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['features']:
                            # Get the most recent earthquake
                            latest = data['features'][0]
                            
                            # Check magnitude
                            magnitude = latest['properties']['mag']
                            if magnitude < 3.5:
                                logger.info(f"Skipping earthquake with magnitude {magnitude}")
                                return
                            
                            # Check if this is a new earthquake
                            if latest['id'] != self.last_quake_id:
                                self.last_quake_id = latest['id']
                                self.last_quake_time = datetime.fromtimestamp(latest['properties']['time'] / 1000)
                                
                                # Post to all enabled channels
                                for guild_id, channel_data in self.feed_channels.items():
                                    if channel_data.get('enabled', True):
                                        channel = self.bot.get_channel(channel_data['channel_id'])
                                        if channel:
                                            # Add guild_id to the feature data
                                            latest['guild_id'] = guild_id
                                            embed = self.create_earthquake_embed(latest)
                                            
                                            # Create view with button
                                            view = discord.ui.View()
                                            view.add_item(discord.ui.Button(
                                                label="View Details",
                                                url=latest['properties']['url'],
                                                style=discord.ButtonStyle.link
                                            ))
                                            
                                            # Get mention roles
                                            mention_roles = channel_data.get('mention_roles', [])
                                            mention_text = " ".join([f"<@&{role_id}>" for role_id in mention_roles]) if mention_roles else ""
                                            
                                            # Send message with mentions if any
                                            if mention_text:
                                                await channel.send(content=mention_text, embed=embed, view=view)
                                            else:
                                                await channel.send(embed=embed, view=view)
                                
                                await self.save_settings()
                                logger.info(f"Posted latest earthquake (M{magnitude})")
        except Exception as e:
            logger.error(f"Error checking most recent earthquake: {e}")

    async def check_earthquakes(self):
        """Check for new earthquakes and post them"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.feed_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data['features']:
                            # Get the most recent earthquake
                            latest = data['features'][0]
                            
                            # Check magnitude
                            magnitude = latest['properties']['mag']
                            if magnitude < 3.5:
                                return
                            
                            # Check if this is a new earthquake
                            if latest['id'] != self.last_quake_id:
                                self.last_quake_id = latest['id']
                                self.last_quake_time = datetime.fromtimestamp(latest['properties']['time'] / 1000)
                                
                                # Post to all enabled channels
                                for guild_id, channel_data in self.feed_channels.items():
                                    if channel_data.get('enabled', True):
                                        channel = self.bot.get_channel(channel_data['channel_id'])
                                        if channel:
                                            # Add guild_id to the feature data
                                            latest['guild_id'] = guild_id
                                            embed = self.create_earthquake_embed(latest)
                                            
                                            # Create view with button
                                            view = discord.ui.View()
                                            view.add_item(discord.ui.Button(
                                                label="View Details",
                                                url=latest['properties']['url'],
                                                style=discord.ButtonStyle.link
                                            ))
                                            
                                            # Get mention roles
                                            mention_roles = channel_data.get('mention_roles', [])
                                            mention_text = " ".join([f"<@&{role_id}>" for role_id in mention_roles]) if mention_roles else ""
                                            
                                            # Send message with mentions if any
                                            if mention_text:
                                                await channel.send(content=mention_text, embed=embed, view=view)
                                            else:
                                                await channel.send(embed=embed, view=view)
                                
                                await self.save_settings()
                                logger.info(f"Posted new earthquake (M{magnitude})")
        except Exception as e:
            logger.error(f"Error checking earthquakes: {e}")

    def create_earthquake_embed(self, feature: Dict) -> discord.Embed:
        """Create an embed for an earthquake event"""
        props = feature['properties']
        coords = feature['geometry']['coordinates']
        
        # Get the color from settings or use default
        guild_id = str(feature.get('guild_id', '0'))
        color = self.feed_channels.get(guild_id, {}).get('embed_color', 0xFF0000)
        
        # Ensure color is an integer
        if isinstance(color, str):
            color = int(color.lstrip('#'), 16)
            
        # Format the time
        quake_time = datetime.fromtimestamp(props['time'] / 1000)
        formatted_time = quake_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Create the description with the requested format
        description = f"A **{props['mag']:.1f}** magnitude earthquake occurred **{props['place']}** @ {formatted_time}"
        
        embed = discord.Embed(
            title="Earthquake Alert:",
            description=description,
            color=color
        )
        
        # Add the earthquake alert image
        embed.set_thumbnail(url="https://i.imgur.com/eE0QEs4.png")
        
        embed.set_footer(text="USGS Earthquake Feed")
        
        return embed

    @app_commands.command(name="earthquake", description="Manage earthquake feed settings")
    @app_commands.guilds(GUILD_ID)
    async def earthquake_command(self, interaction: discord.Interaction):
        """Command to manage earthquake feed settings"""
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You need the 'Manage Channels' permission to use this command.", ephemeral=True)
            return
            
        view = EarthquakeSettingsView(self)
        await interaction.response.send_message("Earthquake Feed Settings:", view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle interactions for the earthquake feed"""
        if not interaction.data:
            return
            
        custom_id = interaction.data.get('custom_id', '')
        
        if custom_id == 'earthquake_channel':
            try:
                channel = interaction.data['values'][0]
                guild_id = str(interaction.guild_id)
                
                # Store channel configuration
                self.feed_channels[guild_id] = {
                    'channel_id': int(channel),
                    'last_quake_time': datetime.utcnow(),
                    'enabled': True,
                    'embed_color': 0xFF0000,
                    'mention_roles': []
                }
                
                # Save settings to file
                await self.save_settings()
                
                embed = discord.Embed(
                    title="✅ Earthquake Feed Setup",
                    description=f"Earthquake feed has been set up in <#{channel}>",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
            except Exception as e:
                logger.error(f"Error setting up earthquake channel: {e}")
                await interaction.response.send_message(
                    "An error occurred while setting up the channel.",
                    ephemeral=True
                )
        elif custom_id == 'earthquake_roles':
            # Ignore this interaction as it's handled by the role_select_callback
            return

async def setup(bot):
    await bot.add_cog(EarthquakeFeed(bot)) 