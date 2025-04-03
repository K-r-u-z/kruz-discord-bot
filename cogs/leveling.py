import discord
from discord import app_commands, ui
from discord.ext import commands
import logging
import json
import os
from typing import Dict, Optional, List
from config import GUILD_ID, BOT_SETTINGS
import random
from datetime import datetime

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

class BaseSettingsView(discord.ui.View):
    def __init__(self, cog: 'Leveling', previous_view=None):
        super().__init__(timeout=120)
        self.cog = cog
        self.previous_view = previous_view

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.gray, row=4)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.previous_view:
            await interaction.response.edit_message(
                embed=create_settings_embed(self.cog),
                view=self.previous_view
            )

class LevelSettingsView(BaseSettingsView):
    def __init__(self, cog: 'Leveling'):
        super().__init__(cog, None)
        self.remove_item(self.back_button)

    @discord.ui.button(label="🔄 Toggle", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.settings["enabled"] = not self.cog.settings.get("enabled", True)
        self.cog._save_settings()
        status = "enabled" if self.cog.settings["enabled"] else "disabled"
        await interaction.response.send_message(
            f"Leveling system {status}!",
            ephemeral=True
        )

    @discord.ui.button(label="📝 Set Channel", style=discord.ButtonStyle.primary)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.settings["log_channel_id"] = interaction.channel.id
        self.cog._save_settings()
        await interaction.response.send_message(
            f"Level-up notifications will now be sent to {interaction.channel.mention}!",
            ephemeral=True
        )

    @discord.ui.button(label="🎭 Manage Roles", style=discord.ButtonStyle.primary)
    async def manage_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = LevelRewardsView(self.cog)
        await interaction.response.edit_message(
            embed=create_role_rewards_embed(self.cog),
            view=view
        )

    @discord.ui.button(label="⚡ XP Multiplier", style=discord.ButtonStyle.primary)
    async def xp_multiplier(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = XPMultiplierView(self.cog, self)
        await interaction.response.edit_message(
            embed=create_xp_multiplier_embed(self.cog),
            view=view
        )

    @discord.ui.button(label="⚙️ XP Settings", style=discord.ButtonStyle.secondary)
    async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = XPSettingsModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🎁 Manage Rewards", style=discord.ButtonStyle.secondary)
    async def manage_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RewardManagementView(self.cog)
        await interaction.response.edit_message(
            embed=create_reward_management_embed(self.cog),
            view=view
        )

    @discord.ui.button(label="📊 Level Cap", style=discord.ButtonStyle.secondary)
    async def level_cap(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = LevelCapModal(self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="👤 Manage User", style=discord.ButtonStyle.secondary)
    async def manage_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = UserManagementView(self.cog)
        await interaction.response.send_message(
            "Select a user and action to manage:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="📝 Message Templates", style=discord.ButtonStyle.secondary)
    async def message_templates(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = MessageTemplatesView(self.cog, self)
        embed = create_message_templates_embed(self.cog)
        await interaction.response.edit_message(embed=embed, view=view)

class LevelRewardsView(discord.ui.View):
    def __init__(self, cog: 'Leveling'):
        super().__init__(timeout=120)
        self.cog = cog
        self.add_role_buttons()

    def add_role_buttons(self):
        for level in sorted(self.cog.level_rewards.keys()):
            button = discord.ui.Button(
                label=f"Level {level}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"role_{level}"
            )
            button.callback = self.make_callback(level)
            self.add_item(button)

    def make_callback(self, level: int):
        async def callback(interaction: discord.Interaction):
            view = RoleRewardView(self.cog, level)
            await interaction.response.send_message(
                f"Select a role for level {level}:",
                view=view,
                ephemeral=True
            )
        return callback

class RoleRewardView(discord.ui.View):
    def __init__(self, cog: 'Leveling', level: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.level = level
        self.add_role_options()

    def add_role_options(self):
        select = discord.ui.Select(
            placeholder="Select a role for this level",
            options=[
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"Set as reward for level {self.level}"
                )
                for role in sorted(self.cog.bot.get_guild(GUILD_ID).roles, key=lambda r: r.name)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        try:
            role_id = int(interaction.data['values'][0])
            role = self.cog.bot.get_guild(GUILD_ID).get_role(role_id)
            
            # Save the role ID
            role_rewards = self.cog.settings.get("role_rewards", {})
            role_rewards[str(self.level)] = role_id
            self.cog.settings["role_rewards"] = role_rewards
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"Set {role.mention} as the reward for level {self.level}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error setting role reward: {e}")
            await interaction.response.send_message(
                "An error occurred while setting the role reward.",
                ephemeral=True
            )

class XPSettingsModal(discord.ui.Modal, title="Configure XP Settings"):
    def __init__(self, cog: 'Leveling'):
        super().__init__()
        self.cog = cog
        
        self.min_xp = discord.ui.TextInput(
            label="Minimum XP per message",
            placeholder="Enter minimum XP (default: 15)",
            default=str(self.cog.settings.get("min_xp", 15)),
            required=True
        )
        
        self.max_xp = discord.ui.TextInput(
            label="Maximum XP per message",
            placeholder="Enter maximum XP (default: 25)",
            default=str(self.cog.settings.get("max_xp", 25)),
            required=True
        )
        
        self.cooldown = discord.ui.TextInput(
            label="Cooldown (seconds)",
            placeholder="Enter cooldown (default: 60)",
            default=str(self.cog.settings.get("xp_cooldown", 60)),
            required=True
        )
        
        self.add_item(self.min_xp)
        self.add_item(self.max_xp)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            min_xp = int(self.min_xp.value)
            max_xp = int(self.max_xp.value)
            cooldown = int(self.cooldown.value)
            
            if min_xp > max_xp:
                await interaction.response.send_message(
                    "Minimum XP cannot be greater than maximum XP!",
                    ephemeral=True
                )
                return
                
            if cooldown < 1:
                await interaction.response.send_message(
                    "Cooldown must be at least 1 second!",
                    ephemeral=True
                )
                return
            
            self.cog.settings["min_xp"] = min_xp
            self.cog.settings["max_xp"] = max_xp
            self.cog.settings["xp_cooldown"] = cooldown
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"XP settings updated!\nMin: {min_xp}\nMax: {max_xp}\nCooldown: {cooldown}s",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid numbers!",
                ephemeral=True
            )

class UserManagementView(discord.ui.View):
    def __init__(self, cog: 'Leveling'):
        super().__init__(timeout=120)
        self.cog = cog
        self.selected_user = None
        self.selected_action = None
        
        # Create user select menu
        self.user_select = discord.ui.Select(
            placeholder="Select a user",
            options=[
                discord.SelectOption(
                    label=member.display_name,
                    value=str(member.id),
                    description=f"ID: {member.id}"
                )
                for member in sorted(cog.bot.get_guild(GUILD_ID).members, key=lambda m: m.display_name)
            ]
        )
        self.user_select.callback = self.on_user_select
        self.add_item(self.user_select)
        
        # Create action select menu
        self.action_select = discord.ui.Select(
            placeholder="Select an action",
            options=[
                discord.SelectOption(
                    label="Add XP",
                    value="add_xp",
                    description="Add XP to user"
                ),
                discord.SelectOption(
                    label="Remove XP",
                    value="remove_xp",
                    description="Remove XP from user"
                ),
                discord.SelectOption(
                    label="Set Level",
                    value="set_level",
                    description="Set user's level directly"
                ),
                discord.SelectOption(
                    label="Force Level Up",
                    value="level_up",
                    description="Force user to level up"
                ),
                discord.SelectOption(
                    label="Reset User",
                    value="reset_user",
                    description="Reset user to level 1 and remove rewards"
                )
            ]
        )
        self.action_select.callback = self.on_action_select
        self.add_item(self.action_select)
        
        # Create amount input button
        self.amount_button = discord.ui.Button(
            label="Enter Amount",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        self.amount_button.callback = self.on_amount_button
        self.add_item(self.amount_button)

    async def on_user_select(self, interaction: discord.Interaction):
        self.selected_user = int(self.user_select.values[0])
        user = interaction.guild.get_member(self.selected_user)
        
        # Update the view with current selections
        await interaction.response.edit_message(
            content=f"Selected user: {user.mention}\n"
                   f"Selected action: {self.selected_action if self.selected_action else 'None'}\n"
                   "Click 'Enter Amount' to proceed." if self.selected_action and self.selected_action != "reset_user" else "Select an action to continue.",
            view=self
        )

    async def on_action_select(self, interaction: discord.Interaction):
        self.selected_action = self.action_select.values[0]
        # Enable the amount button for all actions except reset_user
        self.amount_button.disabled = False
        
        # Update the view with current selections
        await interaction.response.edit_message(
            content=f"Selected user: {interaction.guild.get_member(self.selected_user).mention if self.selected_user else 'None'}\n"
                   f"Selected action: {self.selected_action}\n"
                   "Click 'Enter Amount' to proceed." if self.selected_action != "reset_user" else "Click 'Enter Amount' to confirm reset.",
            view=self
        )

    async def on_amount_button(self, interaction: discord.Interaction):
        if not self.selected_user:
            await interaction.response.send_message(
                "Please select a user first!",
                ephemeral=True
            )
            return
            
        if self.selected_action == "reset_user":
            # Handle reset directly without modal
            user = interaction.guild.get_member(self.selected_user)
            if not user:
                await interaction.response.send_message(
                    "User not found!",
                    ephemeral=True
                )
                return
            
            # Get user data
            user_data = self.cog._get_user_data(user.id)
            
            # Remove all role rewards
            for level in self.cog.settings["role_rewards"].values():
                role = user.guild.get_role(level)
                if role and role in user.roles:
                    try:
                        await user.remove_roles(role)
                    except discord.Forbidden:
                        logger.error(f"Could not remove role {role.name} from {user}")
            
            # Reset user data
            user_data["level"] = 0
            user_data["xp"] = 0
            user_data["total_xp"] = 0  # Reset total XP
            user_data["last_xp_gain"] = 0
            user_data["streak"] = 0
            user_data["last_streak_date"] = None
            user_data["highest_streak"] = 0
            
            # Save changes
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"Reset {user.mention} to level 0, removed all role rewards, and reset all XP.",
                ephemeral=True
            )
            return
            
        if not self.selected_action:
            await interaction.response.send_message(
                "Please select an action first!",
                ephemeral=True
            )
            return
            
        # Create amount input modal for other actions
        modal = AmountInputModal(self.cog, self.selected_user, self.selected_action)
        await interaction.response.send_modal(modal)

class AmountInputModal(discord.ui.Modal, title="Enter Amount"):
    def __init__(self, cog: 'Leveling', user_id: int, action: str):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.action = action
        
        self.amount = discord.ui.TextInput(
            label="Amount",
            placeholder="Enter amount (XP or level)",
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user = interaction.guild.get_member(self.user_id)
            if not user:
                await interaction.response.send_message(
                    "User not found!",
                    ephemeral=True
                )
                return
            
            # Get user data
            user_data = self.cog._get_user_data(user.id)
            amount = int(self.amount.value)
            
            if self.action == "add_xp":
                user_data["xp"] += amount
                await interaction.response.send_message(
                    f"Added {amount} XP to {user.mention}. New total: {user_data['xp']}",
                    ephemeral=True
                )
            
            elif self.action == "remove_xp":
                user_data["xp"] = max(0, user_data["xp"] - amount)
                await interaction.response.send_message(
                    f"Removed {amount} XP from {user.mention}. New total: {user_data['xp']}",
                    ephemeral=True
                )
            
            elif self.action == "set_level":
                if amount < 0:
                    await interaction.response.send_message(
                        "Level must be at least 0!",
                        ephemeral=True
                    )
                    return
                
                # Remove old level rewards
                old_level = user_data["level"]
                for level in self.cog.settings["role_rewards"].values():
                    role = user.guild.get_role(level)
                    if role and role in user.roles:
                        try:
                            await user.remove_roles(role)
                        except discord.Forbidden:
                            logger.error(f"Could not remove role {role.name} from {user}")
                
                # Set new level and reset XP
                user_data["level"] = amount
                user_data["xp"] = 0
                
                # Add new level rewards
                await self.cog._handle_role_rewards(user.id, amount)
                
                await interaction.response.send_message(
                    f"Set {user.mention}'s level to {amount}",
                    ephemeral=True
                )
            
            elif self.action == "level_up":
                old_level = user_data["level"]
                user_data["level"] += amount
                user_data["xp"] = 0  # Reset XP for new level
                
                # Handle level up rewards
                await self.cog._handle_level_up(user, old_level, user_data["level"])
                await self.cog._handle_role_rewards(user.id, user_data["level"])
                
                await interaction.response.send_message(
                    f"Forced {user.mention} to level up {amount} times to level {user_data['level']}",
                    ephemeral=True
                )
            
            # Save changes
            self.cog._save_settings()
            
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in user management: {e}")
            await interaction.response.send_message(
                "An error occurred while managing the user.",
                ephemeral=True
            )

class XPMultiplierView(BaseSettingsView):
    def __init__(self, cog: 'Leveling', previous_view):
        super().__init__(cog, previous_view)
        self.add_multiplier_buttons()

    def add_multiplier_buttons(self):
        # Add buttons for different multiplier actions
        set_global_button = discord.ui.Button(
            label="Set Global Multiplier",
            style=discord.ButtonStyle.primary,
            custom_id="set_global"
        )
        set_global_button.callback = self.set_global_multiplier
        self.add_item(set_global_button)
        
        set_channel_button = discord.ui.Button(
            label="Set Channel Multiplier",
            style=discord.ButtonStyle.primary,
            custom_id="set_channel_mult"
        )
        set_channel_button.callback = self.set_channel_multiplier
        self.add_item(set_channel_button)
        
        remove_button = discord.ui.Button(
            label="Remove Multiplier",
            style=discord.ButtonStyle.danger,
            custom_id="remove_mult"
        )
        remove_button.callback = self.remove_multiplier
        self.add_item(remove_button)

    async def set_global_multiplier(self, interaction: discord.Interaction):
        modal = GlobalMultiplierModal(self.cog)
        await interaction.response.send_modal(modal)

    async def set_channel_multiplier(self, interaction: discord.Interaction):
        modal = ChannelMultiplierModal(self.cog)
        await interaction.response.send_modal(modal)

    async def remove_multiplier(self, interaction: discord.Interaction):
        view = RemoveMultiplierView(self.cog, self)
        await interaction.response.edit_message(
            embed=create_remove_multiplier_embed(self.cog),
            view=view
        )

class GlobalMultiplierModal(discord.ui.Modal, title="Set Global XP Multiplier"):
    def __init__(self, cog: 'Leveling'):
        super().__init__()
        self.cog = cog
        
        self.multiplier = discord.ui.TextInput(
            label="Multiplier",
            placeholder="Enter multiplier (e.g., 2.0 for double XP)",
            default=str(self.cog.settings["xp_multipliers"]["global"]),
            required=True
        )
        
        self.duration = discord.ui.TextInput(
            label="Duration (hours)",
            placeholder="Leave empty for permanent",
            required=False
        )
        
        self.add_item(self.multiplier)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            multiplier = float(self.multiplier.value)
            if multiplier < 0:
                await interaction.response.send_message(
                    "Multiplier cannot be negative!",
                    ephemeral=True
                )
                return
                
            self.cog.settings["xp_multipliers"]["global"] = multiplier
            
            if self.duration.value:
                try:
                    duration = int(self.duration.value)
                    if duration < 1:
                        await interaction.response.send_message(
                            "Duration must be at least 1 hour!",
                            ephemeral=True
                        )
                        return
                    self.cog.settings["xp_multipliers"]["active_until"] = (
                        datetime.now().timestamp() + (duration * 3600)
                    )
                except ValueError:
                    await interaction.response.send_message(
                        "Please enter a valid number for duration!",
                        ephemeral=True
                    )
                    return
            else:
                self.cog.settings["xp_multipliers"]["active_until"] = None
            
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"Global XP multiplier set to {multiplier}x" + 
                (f" for {duration} hours" if self.duration.value else ""),
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number for the multiplier!",
                ephemeral=True
            )

class ChannelMultiplierModal(discord.ui.Modal, title="Set Channel XP Multiplier"):
    def __init__(self, cog: 'Leveling'):
        super().__init__()
        self.cog = cog
        
        self.channel = discord.ui.TextInput(
            label="Channel ID",
            placeholder="Enter channel ID",
            required=True
        )
        
        self.multiplier = discord.ui.TextInput(
            label="Multiplier",
            placeholder="Enter multiplier (e.g., 2.0 for double XP)",
            required=True
        )
        
        self.add_item(self.channel)
        self.add_item(self.multiplier)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel.value)
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Channel not found!",
                    ephemeral=True
                )
                return
                
            multiplier = float(self.multiplier.value)
            if multiplier < 0:
                await interaction.response.send_message(
                    "Multiplier cannot be negative!",
                    ephemeral=True
                )
                return
            
            self.cog.settings["xp_multipliers"]["channels"][str(channel_id)] = multiplier
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"Set XP multiplier to {multiplier}x for {channel.mention}",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid numbers!",
                ephemeral=True
            )

class RemoveMultiplierView(BaseSettingsView):
    def __init__(self, cog: 'Leveling', previous_view):
        super().__init__(cog, previous_view)
        self.add_remove_buttons()

    def add_remove_buttons(self):
        # Add buttons for each channel with a multiplier
        for channel_id, multiplier in self.cog.settings["xp_multipliers"]["channels"].items():
            channel = self.cog.bot.get_channel(int(channel_id))
            if channel:
                button = discord.ui.Button(
                    label=f"Remove {channel.name} ({multiplier}x)",
                    style=discord.ButtonStyle.danger,
                    custom_id=f"remove_{channel_id}",
                    callback=self.make_remove_callback(channel_id)
                )
                self.add_item(button)
        
        # Add button to reset global multiplier
        if self.cog.settings["xp_multipliers"]["global"] != 1.0:
            button = discord.ui.Button(
                label="Reset Global Multiplier",
                style=discord.ButtonStyle.danger,
                custom_id="reset_global",
                callback=self.reset_global_multiplier
            )
            self.add_item(button)

    def make_remove_callback(self, channel_id: str):
        async def callback(interaction: discord.Interaction):
            channel = self.cog.bot.get_channel(int(channel_id))
            if channel:
                del self.cog.settings["xp_multipliers"]["channels"][channel_id]
                self.cog._save_settings()
                await interaction.response.send_message(
                    f"Removed XP multiplier for {channel.mention}",
                    ephemeral=True
                )
        return callback

    async def reset_global_multiplier(self, interaction: discord.Interaction):
        self.cog.settings["xp_multipliers"]["global"] = 1.0
        self.cog.settings["xp_multipliers"]["active_until"] = None
        self.cog._save_settings()
        await interaction.response.send_message(
            "Reset global XP multiplier to 1x",
            ephemeral=True
        )

def create_xp_multiplier_embed(cog: 'Leveling') -> discord.Embed:
    """Create the XP multiplier settings overview embed"""
    embed = discord.Embed(
        title="⚡ XP Multiplier Settings",
        description="Configure XP multipliers for channels or the entire server:",
        color=cog.embed_color
    )
    
    # Add global multiplier info
    global_mult = cog.settings["xp_multipliers"]["global"]
    active_until = cog.settings["xp_multipliers"]["active_until"]
    if active_until:
        time_left = int(active_until - datetime.now().timestamp())
        hours_left = time_left // 3600
        minutes_left = (time_left % 3600) // 60
        embed.add_field(
            name="Global Multiplier",
            value=f"{global_mult}x (expires in {hours_left}h {minutes_left}m)",
            inline=False
        )
    else:
        embed.add_field(
            name="Global Multiplier",
            value=f"{global_mult}x",
            inline=False
        )
    
    # Add channel multipliers
    channel_multipliers = cog.settings["xp_multipliers"]["channels"]
    if channel_multipliers:
        channel_text = ""
        for channel_id, mult in channel_multipliers.items():
            channel = cog.bot.get_channel(int(channel_id))
            if channel:
                channel_text += f"{channel.mention}: {mult}x\n"
        if channel_text:
            embed.add_field(
                name="Channel Multipliers",
                value=channel_text,
                inline=False
            )
    
    return embed

def create_remove_multiplier_embed(cog: 'Leveling') -> discord.Embed:
    """Create the remove multiplier overview embed"""
    embed = discord.Embed(
        title="❌ Remove XP Multipliers",
        description="Select a multiplier to remove:",
        color=cog.embed_color
    )
    
    # Add channel multipliers
    channel_multipliers = cog.settings["xp_multipliers"]["channels"]
    if channel_multipliers:
        channel_text = ""
        for channel_id, mult in channel_multipliers.items():
            channel = cog.bot.get_channel(int(channel_id))
            if channel:
                channel_text += f"{channel.mention}: {mult}x\n"
        if channel_text:
            embed.add_field(
                name="Channel Multipliers",
                value=channel_text,
                inline=False
            )
    
    # Add global multiplier info
    if cog.settings["xp_multipliers"]["global"] != 1.0:
        embed.add_field(
            name="Global Multiplier",
            value=f"Current: {cog.settings['xp_multipliers']['global']}x",
            inline=False
        )
    
    return embed

def create_settings_embed(cog: 'Leveling') -> discord.Embed:
    """Create the settings overview embed"""
    embed = discord.Embed(
        title="⚙️ Leveling System Settings",
        description="Configure the leveling system settings:",
        color=cog.embed_color
    )
    
    # Add system status
    status = "Enabled" if cog.settings.get("enabled", True) else "Disabled"
    embed.add_field(
        name="System Status",
        value=f"Leveling system is currently {status}",
        inline=False
    )
    
    # Add log channel info
    log_channel_id = cog.settings.get("log_channel_id")
    if log_channel_id:
        channel = cog.bot.get_channel(log_channel_id)
        if channel:
            embed.add_field(
                name="Log Channel",
                value=f"Level-up notifications are sent to {channel.mention}",
                inline=False
            )
    
    # Add XP settings
    embed.add_field(
        name="XP Settings",
        value=f"Min XP: {cog.settings.get('min_xp', 15)}\n"
              f"Max XP: {cog.settings.get('max_xp', 25)}\n"
              f"Cooldown: {cog.settings.get('xp_cooldown', 60)}s",
        inline=False
    )
    
    # Add max level info
    max_level = cog.settings.get("max_level", 420)
    embed.add_field(
        name="Maximum Level",
        value=f"Current cap: {max_level}",
        inline=False
    )
    
    return embed

def create_role_rewards_embed(cog: 'Leveling') -> discord.Embed:
    """Create the role rewards overview embed"""
    embed = discord.Embed(
        title="🎭 Role Rewards Management",
        description="Click a level button to set its role reward:",
        color=cog.embed_color
    )
    
    # Add current role rewards
    role_rewards = cog.settings.get("role_rewards", {})
    for level in sorted(cog.level_rewards.keys()):
        role_id = role_rewards.get(str(level))
        role = cog.bot.get_guild(GUILD_ID).get_role(role_id) if role_id else None
        role_info = role.mention if role else "Not set"
        embed.add_field(
            name=f"Level {level}",
            value=f"Role: {role_info}\nReward: {cog.level_rewards[level]}",
            inline=False
        )
    
    return embed

class RewardManagementView(discord.ui.View):
    def __init__(self, cog: 'Leveling'):
        super().__init__(timeout=120)
        self.cog = cog
        self.add_reward_buttons()

    def add_reward_buttons(self):
        # Add button to add new reward
        add_button = discord.ui.Button(
            label="➕ Add New Reward",
            style=discord.ButtonStyle.primary,
            custom_id="add_reward"
        )
        add_button.callback = self.add_reward
        self.add_item(add_button)

        # Add buttons for existing rewards
        for level in sorted(self.cog.level_rewards.keys()):
            # Create a row for each reward with edit and remove buttons
            edit_button = discord.ui.Button(
                label=f"Level {level}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"reward_{level}"
            )
            edit_button.callback = self.make_callback(level)
            self.add_item(edit_button)
            
            remove_button = discord.ui.Button(
                label="❌",
                style=discord.ButtonStyle.danger,
                custom_id=f"remove_{level}"
            )
            remove_button.callback = self.make_remove_callback(level)
            self.add_item(remove_button)

    def make_callback(self, level: int):
        async def callback(interaction: discord.Interaction):
            modal = RewardEditModal(self.cog, level)
            await interaction.response.send_modal(modal)
        return callback

    def make_remove_callback(self, level: int):
        async def callback(interaction: discord.Interaction):
            # Remove the reward
            if level in self.cog.level_rewards:
                del self.cog.level_rewards[level]
                self.cog._save_settings()
                
                # Update the view
                self.clear_items()
                self.add_reward_buttons()
                
                await interaction.response.edit_message(
                    embed=create_reward_management_embed(self.cog),
                    view=self
                )
                
                await interaction.followup.send(
                    f"Removed reward for level {level}!",
                    ephemeral=True
                )
        return callback

    async def add_reward(self, interaction: discord.Interaction):
        modal = NewRewardModal(self.cog)
        await interaction.response.send_modal(modal)

class RewardEditModal(discord.ui.Modal, title="Edit Level Reward"):
    def __init__(self, cog: 'Leveling', level: int):
        super().__init__()
        self.cog = cog
        self.level = level
        
        self.reward = discord.ui.TextInput(
            label="Reward Description",
            placeholder="Enter the reward description",
            default=self.cog.level_rewards.get(level, ""),
            required=True,
            max_length=1000
        )
        self.add_item(self.reward)

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.level_rewards[self.level] = self.reward.value
        self.cog._save_settings()
        await interaction.response.send_message(
            f"Updated reward for level {self.level}!",
            ephemeral=True
        )

class NewRewardModal(discord.ui.Modal, title="Add New Level Reward"):
    def __init__(self, cog: 'Leveling'):
        super().__init__()
        self.cog = cog
        
        self.level = discord.ui.TextInput(
            label="Level",
            placeholder="Enter the level number",
            required=True
        )
        
        self.reward = discord.ui.TextInput(
            label="Reward Description",
            placeholder="Enter the reward description",
            required=True,
            max_length=1000
        )
        
        self.add_item(self.level)
        self.add_item(self.reward)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            level = int(self.level.value)
            if level <= 0:
                await interaction.response.send_message(
                    "Level must be greater than 0!",
                    ephemeral=True
                )
                return
                
            # Convert level to integer key
            self.cog.level_rewards[level] = self.reward.value
            self.cog._save_settings()
            await interaction.response.send_message(
                f"Added new reward for level {level}!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid level number!",
                ephemeral=True
            )

def create_reward_management_embed(cog: 'Leveling') -> discord.Embed:
    """Create the reward management overview embed"""
    embed = discord.Embed(
        title="🎁 Level Rewards Management",
        description="Click a level button to edit its reward, or the ❌ to remove it.\nClick ➕ to add a new reward:",
        color=cog.embed_color
    )
    
    # Add current rewards
    for level in sorted(cog.level_rewards.keys()):
        embed.add_field(
            name=f"Level {level}",
            value=cog.level_rewards[level],
            inline=False
        )
    
    return embed

class LeaderboardView(discord.ui.View):
    def __init__(self, cog: 'Leveling'):
        super().__init__(timeout=120)
        self.cog = cog
        self.current_page = 1
        self.current_sort = "level"
        self.add_sort_buttons()
        self.add_page_buttons()

    def add_sort_buttons(self):
        # Add buttons for different sort options
        level_button = discord.ui.Button(
            label="📈 Sort by Level",
            style=discord.ButtonStyle.primary,
            custom_id="sort_level"
        )
        level_button.callback = self.sort_by_level
        self.add_item(level_button)
        
        xp_button = discord.ui.Button(
            label="💫 Sort by XP",
            style=discord.ButtonStyle.primary,
            custom_id="sort_xp"
        )
        xp_button.callback = self.sort_by_xp
        self.add_item(xp_button)

    def add_page_buttons(self):
        # Add navigation buttons
        prev_button = discord.ui.Button(
            label="◀️ Previous",
            style=discord.ButtonStyle.secondary,
            custom_id="prev_page"
        )
        prev_button.callback = self.prev_page
        self.add_item(prev_button)
        
        next_button = discord.ui.Button(
            label="Next ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="next_page"
        )
        next_button.callback = self.next_page
        self.add_item(next_button)

    async def sort_by_level(self, interaction: discord.Interaction):
        self.current_sort = "level"
        self.current_page = 1
        embed = await self.cog._create_leaderboard_embed(interaction.guild, "level", self.current_page)
        await self.update_button_states(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def sort_by_xp(self, interaction: discord.Interaction):
        self.current_sort = "xp"
        self.current_page = 1
        embed = await self.cog._create_leaderboard_embed(interaction.guild, "xp", self.current_page)
        await self.update_button_states(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 1:
            self.current_page -= 1
            embed = await self.cog._create_leaderboard_embed(interaction.guild, self.current_sort, self.current_page)
            await self.update_button_states(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        embed = await self.cog._create_leaderboard_embed(interaction.guild, self.current_sort, self.current_page)
        await self.update_button_states(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def update_button_states(self, guild: discord.Guild):
        """Update the states of navigation buttons based on current page and total users"""
        # Get total users
        users_data = self.cog.settings.get("users", {})
        sorted_users = [
            member for user_id, data in users_data.items()
            if (member := guild.get_member(int(user_id)))
        ]
        
        # Calculate total pages
        users_per_page = 10
        total_pages = (len(sorted_users) + users_per_page - 1) // users_per_page
        
        # Update button states
        for item in self.children:
            if item.custom_id == "prev_page":
                item.disabled = self.current_page <= 1
            elif item.custom_id == "next_page":
                item.disabled = self.current_page >= total_pages or len(sorted_users) <= users_per_page

class LevelCapModal(discord.ui.Modal, title="Set Maximum Level Cap"):
    def __init__(self, cog: 'Leveling'):
        super().__init__()
        self.cog = cog
        
        self.max_level = discord.ui.TextInput(
            label="Maximum Level",
            placeholder="Enter the maximum level (default: 420)",
            default=str(self.cog.settings.get("max_level", 420)),
            required=True
        )
        self.add_item(self.max_level)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_level = int(self.max_level.value)
            if max_level < 1:
                await interaction.response.send_message(
                    "Maximum level must be at least 1!",
                    ephemeral=True
                )
                return
                
            # Update the max level in settings
            self.cog.settings["max_level"] = max_level
            
            # Update the level rewards dictionary to remove any rewards above the new max level
            self.cog.level_rewards = {
                level: reward for level, reward in self.cog.level_rewards.items()
                if level <= max_level
            }
            
            # Save changes
            self.cog._save_settings()
            
            await interaction.response.send_message(
                f"Maximum level cap set to {max_level}!",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number!",
                ephemeral=True
            )

class Leveling(commands.Cog):
    """Cog for handling user leveling system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.settings = {}
        self.level_rewards = {}
        self.embed_color = discord.Color.blue()
        self.xp_formula = lambda level: 1 if level == 0 else (100 if level == 1 else int(100 * (level ** 1.5)))
        self._load_settings()
        
        # Default rewards if none exist
        if not self.level_rewards:
            self.level_rewards = {
                5: ":art: Custom Nickname - Change your nickname through your profile settings",
                10: ":microphone: Voice Master - Create and manage your own private voice channels",
                15: ":loudspeaker: Join the music channel and listen to your favorite music",
                20: ":video_game: Create your own Clan(role) that stands out and add members",
                40: ":calendar: Post announcements and host your own events and activities for the server",
                50: ":star: Server Veteran - Special recognition and custom role",
                100: ":crown: Server Elite - Custom role with unique color and special permissions",
                200: ":trophy: Legendary Status - Custom role with special perks and recognition",
                300: ":star2: Supreme Status - Custom role with exclusive perks and recognition",
                420: ":herb: Baked Status - Custom role with legendary perks - Level 420"
            }
            self._save_settings()
        else:
            # Convert any string keys to integers
            self.level_rewards = {int(k): v for k, v in self.level_rewards.items()}
            self._save_settings()

    def _load_settings(self):
        """Load settings from file"""
        try:
            with open('data/leveling_settings.json', 'r') as f:
                data = json.load(f)
                self.settings = data.get('settings', {})
                # Convert any string keys to integers when loading
                self.level_rewards = {int(k): v for k, v in data.get('level_rewards', {}).items()}
                
                # Initialize users dictionary if it doesn't exist
                if "users" not in self.settings:
                    self.settings["users"] = {}
                
                # Initialize xp_multipliers if it doesn't exist
                if "xp_multipliers" not in self.settings:
                    self.settings["xp_multipliers"] = {
                        "global": 1.0,
                        "active_until": None,
                        "channels": {},
                        "multiplier_chances": {
                            "10x": 0.001,  # 0.1% chance
                            "5x": 0.005,   # 0.5% chance
                            "2x": 0.02     # 2% chance
                        },
                        "duration_chances": {
                            "30m": 0.4,    # 40% chance
                            "1h": 0.3,     # 30% chance
                            "6h": 0.2,     # 20% chance
                            "12h": 0.07,   # 7% chance
                            "24h": 0.03    # 3% chance
                        }
                    }
                
                # Initialize message templates if they don't exist
                if "message_templates" not in self.settings:
                    self.settings["message_templates"] = {
                        "level_up": "<:levelUp:1356832610470330424> Good Job, {user.mention}, you just advanced to **__Level__** → **__{new_level}__**\n",
                        "level_up_with_reward": "<:levelUp:1356832610470330424> Good Job, {user.mention}, you just advanced to **__Level__** → **__{new_level}__** \n→ You **__UNLOCKED__**  {reward}\n",
                        "multiplier_info": "🎉 You have an active **{amount}x** multiplier for **{duration}**!\n",
                        "next_reward": "Next reward at level {next_level}: {reward}"
                    }
        except FileNotFoundError:
            self.settings = {
                "enabled": True,
                "log_channel_id": None,
                "min_xp": 15,
                "max_xp": 25,
                "xp_cooldown": 60,
                "max_level": 420,
                "users": {},  # Initialize empty users dictionary
                "xp_multipliers": {
                    "global": 1.0,
                    "active_until": None,
                    "channels": {},
                    "multiplier_chances": {
                        "10x": 0.001,  # 0.1% chance
                        "5x": 0.005,   # 0.5% chance
                        "2x": 0.02     # 2% chance
                    },
                    "duration_chances": {
                        "30m": 0.4,    # 40% chance
                        "1h": 0.3,     # 30% chance
                        "6h": 0.2,     # 20% chance
                        "12h": 0.07,   # 7% chance
                        "24h": 0.03    # 3% chance
                    }
                },
                "message_templates": {
                    "level_up": "<:levelUp:1356832610470330424> Good Job, {user.mention}, you just advanced to **__Level__** → **__{new_level}__**\n",
                    "level_up_with_reward": "<:levelUp:1356832610470330424> Good Job, {user.mention}, you just advanced to **__Level__** → **__{new_level}__** \n→ You **__UNLOCKED__**  {reward}\n",
                    "multiplier_info": "🎉 You have an active **{amount}x** multiplier for **{duration}**!\n",
                    "next_reward": "Next reward at level {next_level}: {reward}"
                }
            }
            self._save_settings()

    def _save_settings(self):
        """Save settings to file"""
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data', exist_ok=True)
            
            # Prepare data to save
            data = {
                'settings': self.settings,
                'level_rewards': self.level_rewards
            }
            
            # Save to file
            with open('data/leveling_settings.json', 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving leveling settings: {e}")

    def _get_user_data(self, user_id: int) -> dict:
        """Get user data, creating if it doesn't exist"""
        if str(user_id) not in self.settings["users"]:
            self.settings["users"][str(user_id)] = {
                "xp": 0,
                "level": 0,  # Start at level 0
                "last_xp_gain": 0,
                "streak": 0,
                "last_streak_date": None,
                "highest_streak": 0,
                "total_xp": 0  # Add total_xp field
            }
        return self.settings["users"][str(user_id)]

    def _calculate_level(self, xp: int) -> int:
        """Calculate level based on XP"""
        level = 0
        while self.xp_formula(level) <= xp:
            level += 1
        return level

    def _get_progress_bar(self, current_xp: int, next_level_xp: int, length: int = 10) -> str:
        """Create a progress bar for level progress"""
        if next_level_xp == 0:
            return "[██████████] 100%"
        progress = current_xp / next_level_xp
        filled = int(progress * length)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int(progress * 100)
        return f"[{bar}] {percentage}%"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle message events for XP gain"""
        try:
            if not self.settings.get("enabled", True):
                return
                
            # Ignore bot messages and DMs
            if message.author.bot or not message.guild:
                return
                
            # Get user data
            user_data = self._get_user_data(message.author.id)
            current_time = message.created_at.timestamp()
            
            # Check cooldown using the setting value
            cooldown = self.settings.get("xp_cooldown", 60)
            if current_time - user_data["last_xp_gain"] < cooldown:
                return
                
            # Award XP using the _award_xp method that handles multipliers
            await self._award_xp(message.author.id, message.channel.id)
            
            # Update last gain time
            user_data["last_xp_gain"] = current_time
            self._save_settings()
            
        except Exception as e:
            logger.error(f"Error in on_message event: {str(e)}", exc_info=True)

    async def _handle_level_up(self, user: discord.Member, old_level: int, new_level: int) -> None:
        """Handle level up event"""
        channel_id = self.settings.get("log_channel_id")
        if not channel_id:
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
            
        # Create level up message using templates
        templates = self.settings.get("message_templates", {})
        
        # Check if this is a milestone level
        if new_level in self.level_rewards:
            level_up_msg = templates["level_up_with_reward"].format(
                user=user,
                new_level=new_level,
                reward=self.level_rewards[new_level]
            )
        else:
            level_up_msg = templates["level_up"].format(
                user=user,
                new_level=new_level
            )
        
        # Add multiplier info if applicable
        user_data = self._get_user_data(user.id)
        if "active_multiplier" in user_data:
            multiplier = user_data["active_multiplier"]
            level_up_msg += templates["multiplier_info"].format(
                amount=multiplier["amount"],
                duration=multiplier["duration"]
            )
        
        # Add next reward info if available
        next_reward_level = min(
            (level for level in self.level_rewards.keys() if level > new_level),
            default=None
        )
        if next_reward_level:
            level_up_msg += templates["next_reward"].format(
                next_level=next_reward_level,
                reward=self.level_rewards[next_reward_level]
            )
        
        # Send level up message
        if self.settings.get("log_channel_id"):
            log_channel = self.bot.get_channel(self.settings["log_channel_id"])
            if log_channel:
                await log_channel.send(level_up_msg)
        else:
            await channel.send(level_up_msg)

    async def _handle_role_rewards(self, user_id: int, new_level: int) -> None:
        """Handle role rewards for leveling up"""
        # Get the guild from the bot
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            logger.error("Could not find guild for role rewards")
            return
            
        # Get the member object
        member = guild.get_member(user_id)
        if not member:
            logger.error(f"Could not find member {user_id} for role rewards")
            return
            
        # Get role rewards from settings
        role_rewards = self.settings.get("role_rewards", {})
        
        # Check if there's a role reward for this level
        if str(new_level) in role_rewards:
            role_id = role_rewards[str(new_level)]
            role = guild.get_role(role_id)
            
            if role:
                try:
                    # Remove any previous level roles
                    for level, prev_role_id in role_rewards.items():
                        if int(level) < new_level:
                            prev_role = guild.get_role(prev_role_id)
                            if prev_role and prev_role in member.roles:
                                await member.remove_roles(prev_role)
                    
                    # Add the new role
                    if role not in member.roles:
                        await member.add_roles(role)
                        logger.info(f"Added role {role.name} to {member.name}")
                except Exception as e:
                    logger.error(f"Error handling role rewards: {e}")
            else:
                logger.error(f"Could not find role with ID {role_id}")

    @app_commands.command(
        name="level",
        description="📊 Check your current level and progress"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.cooldown(1, 5)  # 1 use per 5 seconds
    async def check_level(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ) -> None:
        """Check user's level and progress"""
        try:
            target_user = user or interaction.user
            
            # Get user data
            user_data = self._get_user_data(target_user.id)
            current_level = user_data["level"]
            current_xp = user_data["xp"]
            total_xp = user_data.get("total_xp", 0)
            next_level_xp = self.xp_formula(current_level)
            
            # Create progress bar
            progress = self._get_progress_bar(current_xp, next_level_xp)
            
            # Create embed
            embed = discord.Embed(
                title=f"Level Information for {target_user.display_name}",
                color=self.embed_color
            )
            
            embed.add_field(
                name="Current Level",
                value=str(current_level),
                inline=True
            )
            
            embed.add_field(
                name="Current Level XP",
                value=f"{current_xp}/{next_level_xp}",
                inline=True
            )
            
            embed.add_field(
                name="Total XP",
                value=str(total_xp),
                inline=True
            )
            
            embed.add_field(
                name="Progress to Next Level",
                value=progress,
                inline=False
            )
            
            # Add next reward info if available
            next_reward_level = min(
                (level for level in self.level_rewards.keys() if level > current_level),
                default=None
            )
            if next_reward_level:
                embed.add_field(
                    name="Next Reward",
                    value=f"{self.level_rewards[next_reward_level]}",
                    inline=False
                )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Create view with rewards button
            view = discord.ui.View(timeout=120)
            
            # Create the button
            button = discord.ui.Button(
                label="🎁 View All Rewards",
                style=discord.ButtonStyle.primary
            )
            
            # Define the callback
            async def view_rewards_callback(interaction: discord.Interaction):
                rewards_embed = discord.Embed(
                    title="Level Rewards",
                    description="Here are all the available level rewards:",
                    color=self.embed_color
                )
                
                for level, reward in sorted(self.level_rewards.items()):
                    rewards_embed.add_field(
                        name=f"Level {level}",
                        value=reward,
                        inline=False
                    )
                
                await interaction.response.send_message(embed=rewards_embed, ephemeral=True)
            
            # Set the callback
            button.callback = view_rewards_callback
            
            # Add the button to the view
            view.add_item(button)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in level command: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred while checking level.",
                    ephemeral=True
                )

    @app_commands.command(
        name="levelsettings",
        description="⚙️ Configure leveling system settings"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def level_settings(self, interaction: discord.Interaction):
        """Configure leveling system settings"""
        embed = create_settings_embed(self)
        view = LevelSettingsView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="streak",
        description="Check your current streak and streak statistics"
    )
    @app_commands.guilds(GUILD)
    async def streak(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ) -> None:
        """Check streak status"""
        if not user:
            user = interaction.user
            
        user_data = self._get_user_data(user.id)
        
        # Calculate time until streak reset
        if user_data["last_streak_date"]:
            last_date = datetime.fromtimestamp(user_data["last_streak_date"]).date()
            current_date = datetime.now().date()
            days_since_last = (current_date - last_date).days
            
            if days_since_last == 0:
                time_until_reset = "Today"
            elif days_since_last == 1:
                time_until_reset = "Tomorrow"
            else:
                time_until_reset = f"{days_since_last} days ago"
        else:
            time_until_reset = "Never"
        
        # Create embed
        embed = discord.Embed(
            title=f"{user.name}'s Streak Stats",
            color=discord.Color.blue()
        )
        embed.add_field(name="Current Streak", value=f"{user_data['streak']} days", inline=True)
        embed.add_field(name="Highest Streak", value=f"{user_data['highest_streak']} days", inline=True)
        embed.add_field(name="Last Active", value=time_until_reset, inline=True)
        
        # Add streak bonus info
        streak_bonus = min(user_data["streak"] * 0.01, 0.5)
        if streak_bonus > 0:
            embed.add_field(
                name="Streak Bonus",
                value=f"+{int(streak_bonus * 100)}% XP",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="leaderboard",
        description="📊 View the server's leveling leaderboard"
    )
    @app_commands.guilds(GUILD)
    @app_commands.checks.cooldown(1, 30)  # 30 second cooldown
    async def leaderboard(
        self,
        interaction: discord.Interaction
    ) -> None:
        """View the server's leveling leaderboard"""
        try:
            # Create view with sort buttons
            view = LeaderboardView(self)
            
            # Get initial leaderboard (sorted by level)
            embed = await self._create_leaderboard_embed(interaction.guild, "level")
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            await interaction.response.send_message(
                "An error occurred while generating the leaderboard.",
                ephemeral=True
            )

    async def _create_leaderboard_embed(self, guild: discord.Guild, sort_by: str = "level", page: int = 1) -> discord.Embed:
        """Create the leaderboard embed"""
        embed = discord.Embed(
            title="📊 Leveling Leaderboard",
            color=self.embed_color
        )
        
        # Get all user data
        users_data = self.settings.get("users", {})
        
        # Sort users based on the specified criteria
        if sort_by == "level":
            sorted_users = sorted(
                users_data.items(),
                key=lambda x: (x[1]["level"], x[1]["total_xp"]),
                reverse=True
            )
        else:  # sort_by == "xp"
            sorted_users = sorted(
                users_data.items(),
                key=lambda x: x[1]["total_xp"],
                reverse=True
            )
        
        # Calculate pagination
        users_per_page = 10
        total_pages = (len(sorted_users) + users_per_page - 1) // users_per_page
        start_idx = (page - 1) * users_per_page
        end_idx = min(start_idx + users_per_page, len(sorted_users))
        page_users = sorted_users[start_idx:end_idx]
        
        # Add users for current page
        for i, (user_id, data) in enumerate(page_users, start=start_idx + 1):
            user = guild.get_member(int(user_id))
            if user:
                level = data["level"]
                total_xp = data.get("total_xp", 0)
                current_xp = data["xp"]
                next_level_xp = self.xp_formula(level)
                progress = self._get_progress_bar(current_xp, next_level_xp)
                
                # Add medal emoji for top 3
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else ""
                
                embed.add_field(
                    name=f"{medal} {i}. {user.display_name}",
                    value=f"Level: {level}\nTotal XP: {total_xp}\nProgress: {progress}",
                    inline=False
                )
        
        # Add footer with sort info and page
        embed.set_footer(text=f"Sorted by {'Level' if sort_by == 'level' else 'Total XP'} • Page {page}/{total_pages}")
        
        return embed

    def _get_xp_multiplier(self, channel_id: int) -> float:
        """Get the XP multiplier for a channel"""
        # Check channel-specific multiplier first
        channel_mult = self.settings["xp_multipliers"]["channels"].get(str(channel_id), 1.0)
        
        # Check global multiplier
        global_mult = self.settings["xp_multipliers"]["global"]
        active_until = self.settings["xp_multipliers"]["active_until"]
        
        # If global multiplier has expired, reset it
        if active_until and datetime.now().timestamp() > active_until:
            self.settings["xp_multipliers"]["global"] = 1.0
            self.settings["xp_multipliers"]["active_until"] = None
            self._save_settings()
            global_mult = 1.0
        
        # Return the higher multiplier between channel and global
        return max(channel_mult, global_mult)

    async def _check_streak(self, user_id: int) -> None:
        """Check and update user's streak"""
        user_data = self._get_user_data(user_id)
        current_date = datetime.now().date()
        
        # If last streak date is None, this is their first streak
        if user_data["last_streak_date"] is None:
            user_data["streak"] = 1
            user_data["last_streak_date"] = datetime.combine(current_date, datetime.min.time()).timestamp()
            user_data["highest_streak"] = 1
            return
            
        # Convert timestamp to date if it's a timestamp, otherwise use the date directly
        if isinstance(user_data["last_streak_date"], (int, float)):
            last_date = datetime.fromtimestamp(user_data["last_streak_date"]).date()
        else:
            last_date = user_data["last_streak_date"]
        
        # If it's the same day, don't update streak
        if last_date == current_date:
            return
            
        # If it's the next day, increment streak
        if (current_date - last_date).days == 1:
            user_data["streak"] += 1
            if user_data["streak"] > user_data["highest_streak"]:
                user_data["highest_streak"] = user_data["streak"]
        # If it's more than one day, reset streak
        else:
            user_data["streak"] = 1
            
        # Convert date to datetime and then to timestamp
        user_data["last_streak_date"] = datetime.combine(current_date, datetime.min.time()).timestamp()

    async def _award_xp(self, user_id: int, channel_id: int) -> None:
        """Award XP to a user"""
        # Get user data
        user_data = self._get_user_data(user_id)
        current_time = datetime.now().timestamp()
        
        # Check cooldown
        cooldown = self.settings.get("xp_cooldown", 60)
        if current_time - user_data["last_xp_gain"] < cooldown:
            return
        
        # Check and update streak
        await self._check_streak(user_id)
        
        # Get base XP (15-25)
        base_xp = random.randint(15, 25)
        
        # Apply multiplier
        multiplier = self._get_xp_multiplier(channel_id)
        
        # Apply streak bonus (1% per day, up to 50%)
        streak_bonus = min(user_data["streak"] * 0.01, 0.5)
        multiplier *= (1 + streak_bonus)
        
        # Check for random multipliers
        rand = random.random()
        if rand < self.settings["xp_multipliers"]["multiplier_chances"]["10x"]:
            # Determine duration
            duration_rand = random.random()
            duration = None
            for dur, chance in self.settings["xp_multipliers"]["duration_chances"].items():
                if duration_rand < chance:
                    duration = dur
                    break
            
            if duration:
                # Convert duration to seconds
                duration_seconds = {
                    "30m": 1800,  # 30 minutes
                    "1h": 3600,   # 1 hour
                    "6h": 21600,  # 6 hours
                    "12h": 43200, # 12 hours
                    "24h": 86400  # 24 hours
                }[duration]
                
                multiplier *= 10
                user_data["active_multiplier"] = {
                    "amount": 10,
                    "duration": duration,
                    "expires_at": current_time + duration_seconds
                }
        elif rand < self.settings["xp_multipliers"]["multiplier_chances"]["5x"]:
            # Determine duration
            duration_rand = random.random()
            duration = None
            for dur, chance in self.settings["xp_multipliers"]["duration_chances"].items():
                if duration_rand < chance:
                    duration = dur
                    break
            
            if duration:
                # Convert duration to seconds
                duration_seconds = {
                    "30m": 1800,  # 30 minutes
                    "1h": 3600,   # 1 hour
                    "6h": 21600,  # 6 hours
                    "12h": 43200, # 12 hours
                    "24h": 86400  # 24 hours
                }[duration]
                
                multiplier *= 5
                user_data["active_multiplier"] = {
                    "amount": 5,
                    "duration": duration,
                    "expires_at": current_time + duration_seconds
                }
        elif rand < self.settings["xp_multipliers"]["multiplier_chances"]["2x"]:
            # Determine duration
            duration_rand = random.random()
            duration = None
            for dur, chance in self.settings["xp_multipliers"]["duration_chances"].items():
                if duration_rand < chance:
                    duration = dur
                    break
            
            if duration:
                # Convert duration to seconds
                duration_seconds = {
                    "30m": 1800,  # 30 minutes
                    "1h": 3600,   # 1 hour
                    "6h": 21600,  # 6 hours
                    "12h": 43200, # 12 hours
                    "24h": 86400  # 24 hours
                }[duration]
                
                multiplier *= 2
                user_data["active_multiplier"] = {
                    "amount": 2,
                    "duration": duration,
                    "expires_at": current_time + duration_seconds
                }
        
        # Check for active multiplier
        if "active_multiplier" in user_data:
            if current_time < user_data["active_multiplier"]["expires_at"]:
                multiplier *= user_data["active_multiplier"]["amount"]
            else:
                del user_data["active_multiplier"]
        
        # Calculate final XP
        xp_gained = int(base_xp * multiplier)
        
        # Update last gain time
        user_data["last_xp_gain"] = current_time
        
        # Add XP to both current and total
        current_xp = user_data["xp"]
        current_level = user_data["level"]
        user_data["xp"] = current_xp + xp_gained
        user_data["total_xp"] = user_data.get("total_xp", 0) + xp_gained
        
        # Check for level up
        next_level_xp = self.xp_formula(current_level)
        while user_data["xp"] >= next_level_xp:
            user_data["level"] += 1
            user_data["xp"] -= next_level_xp
            next_level_xp = self.xp_formula(user_data["level"])
            
            # Get user and channel objects
            user = self.bot.get_user(user_id)
            channel = self.bot.get_channel(channel_id)
            
            if user and channel:
                # Handle level up event
                await self._handle_level_up(user, current_level, user_data["level"])
                
                # Handle role rewards
                await self._handle_role_rewards(user_id, user_data["level"])
        
        # Save user data
        self._save_settings()

class MessageTemplatesView(discord.ui.View):
    def __init__(self, cog: 'Leveling', previous_view):
        super().__init__(timeout=120)
        self.cog = cog
        self.add_template_buttons()

    def add_template_buttons(self):
        templates = self.cog.settings.get("message_templates", {})
        for template_id, template in templates.items():
            button = discord.ui.Button(
                label=f"Edit {template_id.replace('_', ' ').title()}",
                style=discord.ButtonStyle.primary,
                custom_id=f"edit_{template_id}"
            )
            button.callback = self.make_callback(template_id)
            self.add_item(button)

    def make_callback(self, template_id: str):
        async def callback(interaction: discord.Interaction):
            modal = MessageTemplateModal(self.cog, template_id)
            await interaction.response.send_modal(modal)
        return callback

class MessageTemplateModal(discord.ui.Modal, title="Edit Message Template"):
    def __init__(self, cog: 'Leveling', template_id: str):
        super().__init__()
        self.cog = cog
        self.template_id = template_id
        
        self.template = discord.ui.TextInput(
            label="Message Template",
            placeholder="Enter the message template",
            default=self.cog.settings["message_templates"][template_id],
            required=True,
            max_length=2000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.template)

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.settings["message_templates"][self.template_id] = self.template.value
        self.cog._save_settings()
        await interaction.response.send_message(
            f"Updated {self.template_id.replace('_', ' ').title()} template!",
            ephemeral=True
        )

def create_message_templates_embed(cog: 'Leveling') -> discord.Embed:
    """Create the message templates overview embed"""
    embed = discord.Embed(
        title="📝 Level Message Templates",
        description="Click a button to edit the corresponding message template:",
        color=cog.embed_color
    )
    
    templates = cog.settings.get("message_templates", {})
    for template_id, template in templates.items():
        embed.add_field(
            name=template_id.replace('_', ' ').title(),
            value=f"```{template}```",
            inline=False
        )
    
    return embed

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leveling(bot)) 