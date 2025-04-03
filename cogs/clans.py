import discord
from discord import app_commands, ui
from discord.ext import commands
import logging
import json
import os
from typing import Dict, Optional, List
from config import GUILD_ID, BOT_SETTINGS
import random

logger = logging.getLogger(__name__)
GUILD = discord.Object(id=GUILD_ID)

class ClanCreationModal(discord.ui.Modal, title="Create Your Clan"):
    name = discord.ui.TextInput(
        label="Clan Name",
        placeholder="Enter your clan name",
        required=True,
        min_length=2,
        max_length=32
    )
    
    color = discord.ui.TextInput(
        label="Clan Color (Hex)",
        placeholder="Enter a hex color (e.g. #FF0000)",
        required=True,
        min_length=7,
        max_length=7,
        default="#FF0000"  # Default red color
    )

    def __init__(self, cog: 'Clans'):
        super().__init__()
        self.cog = cog
        # Generate a random hex color for the placeholder
        random_color = f"#{random.randint(0, 0xFFFFFF):06x}".upper()
        self.color.placeholder = f"Enter a hex color (e.g. {random_color})"
        self.color.default = random_color

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user is already in a clan
            for clan in self.cog.clans.values():
                if interaction.user.id in clan["members"]:
                    await interaction.response.send_message(
                        "You are already in a clan!",
                        ephemeral=True
                    )
                    return
            
            # Validate color format
            color = self.color.value.upper()
            if not color.startswith("#"):
                color = f"#{color}"
            
            if not (len(color) == 7 and all(c in "0123456789ABCDEF" for c in color[1:])):
                await interaction.response.send_message(
                    "Invalid color format! Please use a valid hex color (e.g. #FF0000)",
                    ephemeral=True
                )
                return
            
            # Create clan role
            guild = interaction.guild
            role = await guild.create_role(
                name=self.name.value,
                color=discord.Color.from_str(color),
                hoist=True
            )
            
            # Add role to user
            await interaction.user.add_roles(role)
            
            # Create clan data
            clan_data = {
                "name": self.name.value,
                "role_id": role.id,
                "color": color[1:],  # Store without the # prefix
                "members": [interaction.user.id],
                "leader_id": interaction.user.id,
                "description": f"A clan created by {interaction.user.name}",
                "admins": []  # Initialize empty admins list
            }
            
            # Save clan data
            self.cog.clans[str(role.id)] = clan_data
            self.cog._save_clans()
            
            await interaction.response.send_message(
                f"Clan '{self.name.value}' created successfully!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating clan: {e}")
            await interaction.response.send_message(
                "An error occurred while creating the clan.",
                ephemeral=True
            )

class ClanInviteModal(discord.ui.Modal, title="Invite to Clan"):
    def __init__(self, cog: 'Clans', user: discord.Member):
        super().__init__()
        self.cog = cog
        self.user = user
        
        self.message = discord.ui.TextInput(
            label="Invite Message",
            placeholder="Enter a message to send with the invite",
            required=True,
            max_length=200,
            style=discord.TextStyle.paragraph,
            default=f"Join my clan! We're looking for active members to help us grow!"
        )
        
        self.add_item(self.message)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user has a clan
            clan_data = self.cog.clans.get(str(interaction.user.id))
            if not clan_data:
                await interaction.response.send_message(
                    "You don't have a clan!",
                    ephemeral=True
                )
                return
            
            # Check if target user is already in a clan
            if str(self.user.id) in self.cog.clans:
                await interaction.response.send_message(
                    f"{self.user.mention} is already in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is already invited
            if self.user.id in clan_data["invites"]:
                await interaction.response.send_message(
                    f"{self.user.mention} has already been invited to your clan!",
                    ephemeral=True
                )
                return
            
            # Add user to invites list
            clan_data["invites"].append(self.user.id)
            self.cog._save_clans()
            
            # Create invite embed
            role = interaction.guild.get_role(clan_data["role_id"])
            if not role:
                await interaction.response.send_message(
                    "Error: Clan role not found!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🏰 Clan Invitation: {clan_data['name']}",
                description=self.message.value,
                color=role.color
            )
            embed.add_field(name="Clan Description", value=clan_data["description"], inline=False)
            embed.add_field(name="Leader", value=interaction.user.mention, inline=True)
            embed.add_field(name="Members", value=str(len(clan_data["members"])), inline=True)
            
            # Create view with accept/deny buttons
            view = discord.ui.View(timeout=300)  # 5 minutes timeout
            
            async def accept_callback(interaction: discord.Interaction):
                try:
                    # Check if user is still invited
                    if self.user.id not in clan_data["invites"]:
                        await interaction.response.send_message(
                            "This invite has expired!",
                            ephemeral=True
                        )
                        return
                    
                    # Add user to clan
                    clan_data["invites"].remove(self.user.id)
                    clan_data["members"].append(self.user.id)
                    self.cog._save_clans()
                    
                    # Add role to user
                    await self.user.add_roles(role)
                    
                    await interaction.response.send_message(
                        f"Welcome to {clan_data['name']}!",
                        ephemeral=True
                    )
                    
                except Exception as e:
                    logger.error(f"Error accepting clan invite: {e}")
                    await interaction.response.send_message(
                        "An error occurred while accepting the invite.",
                        ephemeral=True
                    )
            
            async def deny_callback(interaction: discord.Interaction):
                try:
                    # Remove user from invites
                    if self.user.id in clan_data["invites"]:
                        clan_data["invites"].remove(self.user.id)
                        self.cog._save_clans()
                    
                    await interaction.response.send_message(
                        "You have declined the clan invitation.",
                        ephemeral=True
                    )
                    
                except Exception as e:
                    logger.error(f"Error declining clan invite: {e}")
                    await interaction.response.send_message(
                        "An error occurred while declining the invite.",
                        ephemeral=True
                    )
            
            accept_button = discord.ui.Button(
                label="Accept",
                style=discord.ButtonStyle.success,
                custom_id="accept_invite"
            )
            accept_button.callback = accept_callback
            
            deny_button = discord.ui.Button(
                label="Decline",
                style=discord.ButtonStyle.danger,
                custom_id="deny_invite"
            )
            deny_button.callback = deny_callback
            
            view.add_item(accept_button)
            view.add_item(deny_button)
            
            # Send invite to target user
            try:
                await self.user.send(embed=embed, view=view)
                await interaction.response.send_message(
                    f"Invited {self.user.mention} to your clan!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    f"I couldn't send a DM to {self.user.mention}. They might have DMs disabled.",
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f"Error sending clan invite: {e}")
            await interaction.response.send_message(
                "An error occurred while sending the invite.",
                ephemeral=True
            )

class ColorChangeModal(discord.ui.Modal, title="Change Clan Color"):
    def __init__(self, cog: 'Clans'):
        super().__init__()
        self.cog = cog
        
        self.color = discord.ui.TextInput(
            label="New Color (Hex)",
            placeholder="Enter hex color (e.g., #FF0000)",
            required=True,
            max_length=7,
            default="#" + ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
        )
        
        self.add_item(self.color)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader or admin
            if interaction.user.id not in [user_clan["leader_id"], *user_clan.get("admins", [])]:
                await interaction.response.send_message(
                    "Only the clan leader or an admin can change the clan color!",
                    ephemeral=True
                )
                return
            
            # Get the role
            role = interaction.guild.get_role(user_clan["role_id"])
            if not role:
                await interaction.response.send_message(
                    "Error: Clan role not found!",
                    ephemeral=True
                )
                return
            
            # Update the color
            try:
                color = int(self.color.value.replace("#", ""), 16)
                await role.edit(color=discord.Color(color))
                
                await interaction.response.send_message(
                    f"Successfully changed {user_clan['name']}'s color!",
                    ephemeral=True
                )
                
            except ValueError:
                await interaction.response.send_message(
                    "Invalid color format! Please use a valid hex color (e.g., #FF0000)",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to change the role color!",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error changing clan color: {e}")
            await interaction.response.send_message(
                "An error occurred while changing the clan color.",
                ephemeral=True
            )

class NameChangeModal(discord.ui.Modal, title="Change Clan Name"):
    def __init__(self, cog: 'Clans'):
        super().__init__()
        self.cog = cog
        
        self.name = discord.ui.TextInput(
            label="New Clan Name",
            placeholder="Enter new clan name",
            required=True,
            max_length=32,
            style=discord.TextStyle.short
        )
        
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader or admin
            if interaction.user.id not in [user_clan["leader_id"], *user_clan.get("admins", [])]:
                await interaction.response.send_message(
                    "Only the clan leader or an admin can change the clan name!",
                    ephemeral=True
                )
                return
            
            # Get the role
            role = interaction.guild.get_role(user_clan["role_id"])
            if not role:
                await interaction.response.send_message(
                    "Error: Clan role not found!",
                    ephemeral=True
                )
                return
            
            # Update the name
            try:
                old_name = user_clan["name"]
                await role.edit(name=self.name.value)
                user_clan["name"] = self.name.value
                self.cog._save_clans()
                
                await interaction.response.send_message(
                    f"Successfully renamed your clan from {old_name} to {self.name.value}!",
                    ephemeral=True
                )
                
            except discord.Forbidden:
                await interaction.response.send_message(
                    "I don't have permission to change the role name!",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error changing clan name: {e}")
            await interaction.response.send_message(
                "An error occurred while changing the clan name.",
                ephemeral=True
            )

class ClanView(discord.ui.View):
    def __init__(self, cog: 'Clans'):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog

    @discord.ui.button(label="Create Clan", style=discord.ButtonStyle.primary, emoji="🏰")
    async def create_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user has the level 20 role (only if leveling is enabled)
            leveling_cog = self.cog.bot.get_cog("Leveling")
            if leveling_cog and leveling_cog.settings.get("enabled", True):
                role_rewards = leveling_cog.settings.get("role_rewards", {})
                level_20_role_id = role_rewards.get("20")
                
                if level_20_role_id:
                    level_20_role = interaction.guild.get_role(level_20_role_id)
                    if level_20_role and level_20_role not in interaction.user.roles:
                        await interaction.response.send_message(
                            f"You don't have the required role for clan creation. {level_20_role.name} required",
                            ephemeral=True
                        )
                        return
            
            # Check if user already has a clan
            if str(interaction.user.id) in self.cog.clans:
                await interaction.response.send_message(
                    "You already have a clan!",
                    ephemeral=True
                )
                return
            
            # Show creation modal
            modal = ClanCreationModal(self.cog)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in create clan button: {e}")
            await interaction.response.send_message(
                "An error occurred while creating your clan.",
                ephemeral=True
            )

    @discord.ui.button(label="Invite Member", style=discord.ButtonStyle.success, emoji="📨")
    async def invite_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in any clan
            clan_data = None
            for clan in self.cog.clans.values():
                if interaction.user.id in clan["members"]:
                    clan_data = clan
                    break
            
            if not clan_data:
                await interaction.response.send_message(
                    "You are not in any clan!",
                    ephemeral=True
                )
                return
            
            # Create and send the user select view
            view = UserSelectView(self.cog)
            await interaction.response.send_message(
                "Select a user to invite to your clan:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in invite member button: {e}")
            await interaction.response.send_message(
                "An error occurred while inviting a member.",
                ephemeral=True
            )

    @discord.ui.button(label="Leave Clan", style=discord.ButtonStyle.danger, emoji="👋")
    async def leave_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader
            if interaction.user.id == user_clan["leader_id"]:
                await interaction.response.send_message(
                    "You can't leave your own clan! Use the Delete Clan button instead.",
                    ephemeral=True
                )
                return
            
            # Remove user from clan
            user_clan["members"].remove(interaction.user.id)
            self.cog._save_clans()
            
            # Remove role
            role = interaction.guild.get_role(user_clan["role_id"])
            if role:
                await interaction.user.remove_roles(role)
            
            await interaction.response.send_message(
                f"You have left {user_clan['name']}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in leave clan button: {e}")
            await interaction.response.send_message(
                "An error occurred while leaving your clan.",
                ephemeral=True
            )

    @discord.ui.button(label="Delete Clan", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Find the clan where the user is the leader
            clan_data = None
            for clan in self.cog.clans.values():
                if interaction.user.id == clan["leader_id"]:
                    clan_data = clan
                    break
            
            if not clan_data:
                await interaction.response.send_message(
                    "You are not the leader of any clan!",
                    ephemeral=True
                )
                return
            
            # Create confirmation view
            view = discord.ui.View()
            
            # Create confirm button
            confirm_button = discord.ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="confirm_delete"
            )
            
            async def confirm_callback(interaction: discord.Interaction):
                try:
                    # Get the guild and role
                    guild = self.cog.bot.get_guild(GUILD_ID)
                    if not guild:
                        await interaction.response.send_message(
                            "Could not find the guild!",
                            ephemeral=True
                        )
                        return
                    
                    role = guild.get_role(clan_data["role_id"])
                    if role:
                        await role.delete()
                    
                    # Remove clan from data
                    del self.cog.clans[str(clan_data["role_id"])]
                    self.cog._save_clans()
                    
                    await interaction.response.send_message(
                        f"Clan '{clan_data['name']}' has been deleted!",
                        ephemeral=True
                    )
                except Exception as e:
                    logger.error(f"Error in confirm delete callback: {e}")
                    await interaction.response.send_message(
                        "An error occurred while deleting the clan.",
                        ephemeral=True
                    )
            
            confirm_button.callback = confirm_callback
            view.add_item(confirm_button)
            
            # Create cancel button
            cancel_button = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
                custom_id="cancel_delete"
            )
            
            async def cancel_callback(interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Clan deletion cancelled.",
                    ephemeral=True
                )
            
            cancel_button.callback = cancel_callback
            view.add_item(cancel_button)
            
            await interaction.response.send_message(
                f"Are you sure you want to delete the clan '{clan_data['name']}'? This action cannot be undone!",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in delete clan button: {e}")
            await interaction.response.send_message(
                "An error occurred while deleting the clan.",
                ephemeral=True
            )

    @discord.ui.button(label="Transfer Leadership", style=discord.ButtonStyle.primary, emoji="👑")
    async def transfer_leadership(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader
            if interaction.user.id != user_clan["leader_id"]:
                await interaction.response.send_message(
                    "Only the clan leader can transfer leadership!",
                    ephemeral=True
                )
                return
            
            # Create user selection modal
            modal = LeadershipTransferModal(self.cog)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in transfer leadership button: {e}")
            await interaction.response.send_message(
                "An error occurred while transferring leadership.",
                ephemeral=True
            )

    @discord.ui.button(label="View Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def view_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_data in self.cog.clans.values():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Create info embed
            role = interaction.guild.get_role(user_clan["role_id"])
            if not role:
                await interaction.response.send_message(
                    "Error: Clan role not found!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🏰 Clan: {user_clan['name']}",
                description=user_clan["description"],
                color=role.color
            )
            
            # Add leader info
            leader = interaction.guild.get_member(user_clan["leader_id"])
            embed.add_field(
                name="Leader",
                value=leader.mention if leader else "Unknown",
                inline=True
            )
            
            # Add member count
            embed.add_field(
                name="Members",
                value=str(len(user_clan["members"])),
                inline=True
            )
            
            # Add member list
            member_list = []
            for member_id in user_clan["members"]:
                member = interaction.guild.get_member(member_id)
                if member:
                    member_list.append(member.mention)
            
            if member_list:
                embed.add_field(
                    name="Member List",
                    value="\n".join(member_list),
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in view info button: {e}")
            await interaction.response.send_message(
                "An error occurred while viewing clan information.",
                ephemeral=True
            )

    @discord.ui.button(label="List Clans", style=discord.ButtonStyle.secondary, emoji="📋")
    async def list_clans(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not self.cog.clans:
                await interaction.response.send_message(
                    "There are no clans yet!",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title="🏰 Server Clans",
                description="Here are all the clans in the server:",
                color=discord.Color.blue()
            )
            
            # Sort clans by member count
            sorted_clans = sorted(
                self.cog.clans.values(),
                key=lambda x: len(x["members"]),
                reverse=True
            )
            
            for clan_data in sorted_clans:
                role = interaction.guild.get_role(clan_data["role_id"])
                if not role:
                    continue
                
                leader = interaction.guild.get_member(clan_data["leader_id"])
                leader_name = leader.mention if leader else "Unknown"
                
                member_count = len(clan_data["members"])
                value = f"👑 Leader: {leader_name}\n👥 Members: {member_count}"
                
                embed.add_field(
                    name=f"{role.color} {clan_data['name']}",
                    value=value,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in list clans button: {e}")
            await interaction.response.send_message(
                "An error occurred while listing clans.",
                ephemeral=True
            )

    @discord.ui.button(label="Change Color", style=discord.ButtonStyle.primary, emoji="🎨")
    async def change_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader or admin
            if interaction.user.id not in [user_clan["leader_id"], *user_clan.get("admins", [])]:
                await interaction.response.send_message(
                    "Only the clan leader or an admin can change the clan color!",
                    ephemeral=True
                )
                return
            
            # Show color change modal
            modal = ColorChangeModal(self.cog)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in change color button: {e}")
            await interaction.response.send_message(
                "An error occurred while changing the clan color.",
                ephemeral=True
            )

    @discord.ui.button(label="Change Name", style=discord.ButtonStyle.primary, emoji="✏️")
    async def change_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader or admin
            if interaction.user.id not in [user_clan["leader_id"], *user_clan.get("admins", [])]:
                await interaction.response.send_message(
                    "Only the clan leader or an admin can change the clan name!",
                    ephemeral=True
                )
                return
            
            # Show name change modal
            modal = NameChangeModal(self.cog)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in change name button: {e}")
            await interaction.response.send_message(
                "An error occurred while changing the clan name.",
                ephemeral=True
            )

    @discord.ui.button(label="Promote/Demote", style=discord.ButtonStyle.primary, emoji="👑")
    async def promote_demote(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is a clan leader
            clan_data = self.cog.clans.get(str(interaction.user.id))
            if not clan_data:
                await interaction.response.send_message(
                    "You are not a clan leader!",
                    ephemeral=True
                )
                return
            
            # Create member select view
            view = MemberSelectView(self.cog, clan_data)
            await interaction.response.send_message(
                "Select a member to promote/demote:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in promote/demote button: {e}")
            await interaction.response.send_message(
                "An error occurred while promoting/demoting a member.",
                ephemeral=True
            )

    @discord.ui.button(label="Remove Member", style=discord.ButtonStyle.danger, emoji="🚫")
    async def remove_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Check if user is clan leader or admin
            clan_data = None
            for clan in self.cog.clans.values():
                if interaction.user.id in clan["members"]:
                    if interaction.user.id == clan["leader_id"] or interaction.user.id in clan.get("admins", []):
                        clan_data = clan
                        break
            
            if not clan_data:
                await interaction.response.send_message(
                    "You don't have permission to remove members!",
                    ephemeral=True
                )
                return
            
            # Create member select view
            view = RemoveMemberView(self.cog, clan_data, interaction.user.id == clan_data["leader_id"])
            await interaction.response.send_message(
                "Select a member to remove from the clan:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in remove member button: {e}")
            await interaction.response.send_message(
                "An error occurred while removing a member.",
                ephemeral=True
            )

class UserSelectView(discord.ui.View):
    def __init__(self, cog: 'Clans'):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.selected_user = None
        
        # Create the user select component
        self.user_select = discord.ui.UserSelect(
            placeholder="Select a user to invite",
            min_values=1,
            max_values=1,
            custom_id="user_select"
        )
        self.user_select.callback = self.user_select_callback
        self.add_item(self.user_select)
    
    async def user_select_callback(self, interaction: discord.Interaction):
        try:
            selected_user = self.user_select.values[0]
            
            # Check if user is already in a clan
            for clan in self.cog.clans.values():
                if selected_user.id in clan["members"]:
                    await interaction.response.send_message(
                        f"{selected_user.mention} is already in a clan!",
                        ephemeral=True
                    )
                    return
            
            # Get the clan of the inviter
            clan = self.cog.clans.get(str(interaction.user.id))
            if not clan:
                await interaction.response.send_message(
                    "You don't have a clan to invite members to!",
                    ephemeral=True
                )
                return
            
            # Create invite embed
            embed = discord.Embed(
                title="Clan Invitation",
                description=f"{selected_user.mention}, you have been invited to join **{clan['name']}**!",
                color=discord.Color(int(clan["color"], 16))
            )
            embed.add_field(
                name="Invited by",
                value=interaction.user.mention,
                inline=False
            )
            embed.add_field(
                name="Description",
                value=clan["description"],
                inline=False
            )
            
            # Create accept/deny buttons
            view = discord.ui.View()
            
            # Create accept button
            accept_button = discord.ui.Button(
                label="Accept",
                style=discord.ButtonStyle.success,
                custom_id="accept_invite"
            )
            
            async def accept_callback(interaction: discord.Interaction):
                if interaction.user.id != selected_user.id:
                    await interaction.response.send_message(
                        "This invitation is not for you!",
                        ephemeral=True
                    )
                    return
                
                # Get the guild and role
                guild = self.cog.bot.get_guild(GUILD_ID)
                if not guild:
                    await interaction.response.send_message(
                        "Could not find the server. Please try again later.",
                        ephemeral=True
                    )
                    return
                
                role = guild.get_role(clan["role_id"])
                if not role:
                    await interaction.response.send_message(
                        "Could not find the clan role. Please contact an administrator.",
                        ephemeral=True
                    )
                    return
                
                # Add user to clan
                clan["members"].append(selected_user.id)
                await selected_user.add_roles(role)
                
                self.cog._save_clans()
                
                await interaction.response.send_message(
                    f"You have joined **{clan['name']}**!",
                    ephemeral=True
                )
            
            accept_button.callback = accept_callback
            view.add_item(accept_button)
            
            # Create deny button
            deny_button = discord.ui.Button(
                label="Decline",
                style=discord.ButtonStyle.danger,
                custom_id="deny_invite"
            )
            
            async def deny_callback(interaction: discord.Interaction):
                if interaction.user.id != selected_user.id:
                    await interaction.response.send_message(
                        "This invitation is not for you!",
                        ephemeral=True
                    )
                    return
                
                await interaction.response.send_message(
                    "You have declined the invitation.",
                    ephemeral=True
                )
            
            deny_button.callback = deny_callback
            view.add_item(deny_button)
            
            # Send invitation
            await selected_user.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"Invitation sent to {selected_user.mention}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in user select callback: {e}")
            await interaction.response.send_message(
                "An error occurred while selecting the user.",
                ephemeral=True
            )

class LeadershipTransferModal(discord.ui.Modal, title="Transfer Clan Leadership"):
    def __init__(self, cog: 'Clans'):
        super().__init__()
        self.cog = cog
        
        self.user = discord.ui.TextInput(
            label="User ID or Mention",
            placeholder="Enter user ID or mention",
            required=True,
            max_length=20,
            style=discord.TextStyle.short
        )
        
        self.add_item(self.user)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check if user is in a clan
            user_clan = None
            for clan_id, clan_data in self.cog.clans.items():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if not user_clan:
                await interaction.response.send_message(
                    "You're not in a clan!",
                    ephemeral=True
                )
                return
            
            # Check if user is the leader
            if interaction.user.id != user_clan["leader_id"]:
                await interaction.response.send_message(
                    "Only the clan leader can transfer leadership!",
                    ephemeral=True
                )
                return
            
            # Parse user input
            user_input = self.user.value.strip()
            new_leader = None
            
            # Try to get user from mention
            if user_input.startswith("<@") and user_input.endswith(">"):
                user_id = int(user_input[2:-1].replace("!", ""))
                new_leader = interaction.guild.get_member(user_id)
            
            # Try to get user from ID
            if not new_leader and user_input.isdigit():
                new_leader = interaction.guild.get_member(int(user_input))
            
            if not new_leader:
                await interaction.response.send_message(
                    "Could not find the specified user!",
                    ephemeral=True
                )
                return
            
            # Check if new leader is in the clan
            if new_leader.id not in user_clan["members"]:
                await interaction.response.send_message(
                    f"{new_leader.mention} is not a member of your clan!",
                    ephemeral=True
                )
                return
            
            # Transfer leadership
            user_clan["leader_id"] = new_leader.id
            self.cog._save_clans()
            
            await interaction.response.send_message(
                f"Leadership of {user_clan['name']} has been transferred to {new_leader.mention}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in leadership transfer modal: {e}")
            await interaction.response.send_message(
                "An error occurred while transferring leadership.",
                ephemeral=True
            )

class MemberSelectView(discord.ui.View):
    def __init__(self, cog: 'Clans', clan_data: dict):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.clan_data = clan_data
        
        # Create the member select component
        self.member_select = discord.ui.UserSelect(
            placeholder="Select a clan member",
            min_values=1,
            max_values=1,
            custom_id="member_select"
        )
        self.member_select.callback = self.member_select_callback
        self.add_item(self.member_select)
    
    async def member_select_callback(self, interaction: discord.Interaction):
        try:
            selected_member = self.member_select.values[0]
            
            # Check if selected member is in the clan
            if selected_member.id not in self.clan_data["members"]:
                await interaction.response.send_message(
                    f"{selected_member.mention} is not in your clan!",
                    ephemeral=True
                )
                return
            
            # Don't allow promoting/demoting the leader
            if selected_member.id == self.clan_data["leader_id"]:
                await interaction.response.send_message(
                    "You cannot promote/demote the clan leader!",
                    ephemeral=True
                )
                return
            
            # Create promote/demote buttons
            view = discord.ui.View()
            
            # Create promote button
            promote_button = discord.ui.Button(
                label="Promote",
                style=discord.ButtonStyle.success,
                custom_id="promote_member"
            )
            
            async def promote_callback(interaction: discord.Interaction):
                # Ensure admins list exists
                if "admins" not in self.clan_data:
                    self.clan_data["admins"] = []
                
                # Add admin permissions to the member
                self.clan_data["admins"].append(selected_member.id)
                self.cog._save_clans()
                
                await interaction.response.send_message(
                    f"{selected_member.mention} has been promoted to clan admin!",
                    ephemeral=True
                )
            
            promote_button.callback = promote_callback
            view.add_item(promote_button)
            
            # Create demote button
            demote_button = discord.ui.Button(
                label="Demote",
                style=discord.ButtonStyle.danger,
                custom_id="demote_member"
            )
            
            async def demote_callback(interaction: discord.Interaction):
                # Remove admin permissions from the member
                if selected_member.id in self.clan_data["admins"]:
                    self.clan_data["admins"].remove(selected_member.id)
                    self.cog._save_clans()
                    
                    await interaction.response.send_message(
                        f"{selected_member.mention} has been demoted from clan admin!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"{selected_member.mention} is not a clan admin!",
                        ephemeral=True
                    )
            
            demote_button.callback = demote_callback
            view.add_item(demote_button)
            
            await interaction.response.send_message(
                f"Select an action for {selected_member.mention}:",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in member select callback: {e}")
            await interaction.response.send_message(
                "An error occurred while selecting the member.",
                ephemeral=True
            )

class RemoveMemberView(discord.ui.View):
    def __init__(self, cog: 'Clans', clan_data: dict, is_leader: bool):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.clan_data = clan_data
        self.is_leader = is_leader
        
        # Create the member select component
        self.member_select = discord.ui.UserSelect(
            placeholder="Select a member to remove",
            min_values=1,
            max_values=1,
            custom_id="remove_member_select"
        )
        self.member_select.callback = self.member_select_callback
        self.add_item(self.member_select)
    
    async def member_select_callback(self, interaction: discord.Interaction):
        try:
            selected_member = self.member_select.values[0]
            
            # Check if selected member is in the clan
            if selected_member.id not in self.clan_data["members"]:
                await interaction.response.send_message(
                    f"{selected_member.mention} is not in your clan!",
                    ephemeral=True
                )
                return
            
            # Check if trying to remove the leader
            if selected_member.id == self.clan_data["leader_id"]:
                await interaction.response.send_message(
                    "You cannot remove the clan leader!",
                    ephemeral=True
                )
                return
            
            # Check if admin is trying to remove another admin
            if not self.is_leader and selected_member.id in self.clan_data.get("admins", []):
                await interaction.response.send_message(
                    "Only the clan leader can remove admins!",
                    ephemeral=True
                )
                return
            
            # Create confirmation view
            view = discord.ui.View()
            
            # Create confirm button
            confirm_button = discord.ui.Button(
                label="Confirm",
                style=discord.ButtonStyle.danger,
                custom_id="confirm_remove"
            )
            
            async def confirm_callback(interaction: discord.Interaction):
                # Remove member from clan
                self.clan_data["members"].remove(selected_member.id)
                
                # Remove from admins if they were an admin
                if selected_member.id in self.clan_data.get("admins", []):
                    self.clan_data["admins"].remove(selected_member.id)
                
                # Remove clan role
                guild = self.cog.bot.get_guild(GUILD_ID)
                if guild:
                    role = guild.get_role(self.clan_data["role_id"])
                    if role:
                        await selected_member.remove_roles(role)
                
                self.cog._save_clans()
                
                await interaction.response.send_message(
                    f"{selected_member.mention} has been removed from the clan!",
                    ephemeral=True
                )
            
            confirm_button.callback = confirm_callback
            view.add_item(confirm_button)
            
            # Create cancel button
            cancel_button = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.secondary,
                custom_id="cancel_remove"
            )
            
            async def cancel_callback(interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Member removal cancelled.",
                    ephemeral=True
                )
            
            cancel_button.callback = cancel_callback
            view.add_item(cancel_button)
            
            await interaction.response.send_message(
                f"Are you sure you want to remove {selected_member.mention} from the clan?",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in remove member callback: {e}")
            await interaction.response.send_message(
                "An error occurred while removing the member.",
                ephemeral=True
            )

class Clans(commands.Cog):
    """Cog for managing custom roles (clans)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.clans = self._load_clans()
        
        # Initialize admins list for existing clans
        for clan in self.clans.values():
            if "admins" not in clan:
                clan["admins"] = []

    def _load_clans(self):
        """Load clans from file"""
        try:
            with open('data/clans.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            logger.error("Error decoding clans.json")
            return {}

    def _save_clans(self):
        """Save clans to file"""
        try:
            with open('data/clans.json', 'w') as f:
                json.dump(self.clans, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving clans: {e}")

    @app_commands.command(
        name="clan",
        description="Manage your clan"
    )
    @app_commands.guilds(GUILD)
    async def clan(self, interaction: discord.Interaction) -> None:
        """Manage your clan"""
        try:
            # Create embed
            embed = discord.Embed(
                title="🏰 Clan Management",
                description="Choose an action to manage your clan:",
                color=discord.Color.blue()
            )
            
            # Add user's clan status
            user_clan = None
            for clan_data in self.clans.values():
                if interaction.user.id in clan_data["members"]:
                    user_clan = clan_data
                    break
            
            if user_clan:
                embed.add_field(
                    name="Your Clan",
                    value=f"🏰 {user_clan['name']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Your Status",
                    value="You are not in a clan",
                    inline=False
                )
            
            # Create view with buttons
            view = ClanView(self)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in clan command: {e}")
            await interaction.response.send_message(
                "An error occurred while managing your clan.",
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Clans(bot)) 