import os
import asyncio

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext, ComponentContext
from discord_slash.utils.manage_commands import create_option, create_choice, create_permission
from discord_slash.utils import manage_components
from discord_slash.model import SlashCommandOptionType, ButtonStyle, SlashCommandPermissionType


FEEDBACK_CHANNEL = 872104333007785984
FEEDBACK_MENTION = 872107119988588566
ADMIN_GUILD = int(os.getenv('ADMIN_GUILD'))

class AdminModule(commands.Cog):
    
    def __init__(self, client):
        self.client = client
    
    # =====================
    # helper methods
    # =====================
    
    # =====================
    # events functions
    # =====================
    
    
    @commands.Cog.listener()
    async def on_ready(self):
        print('AdminModule loaded')
        
    # =====================
    # commands functions
    # =====================
    
    @cog_ext.cog_slash(name='load', guild_ids=[ADMIN_GUILD], description='Load a newly added Cog',
                        default_permission=False,
                        permissions={
                            ADMIN_GUILD: [
                                create_permission(
                                id=140149964020908032,  # owner
                                id_type=SlashCommandPermissionType.USER,
                                permission=True
                                )
                            ]
                        },
                        options=[
                            create_option(
                                name='module',
                                description='name of the module',
                                required=True,
                                option_type=SlashCommandOptionType.STRING,
                            )
                        ])
    async def load_module(self, ctx, module):
        await ctx.defer(hidden=True)  # reload may take a while

        try:
            self.client.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}', hidden=True)
        else:
            await ctx.send('\N{OK HAND SIGN}', hidden=True)
            print(f'Reloaded Module: {module}')


    @cog_ext.cog_slash(name='reload', guild_ids=[ADMIN_GUILD], description='Reload an updated added Cog',
                        default_permission=False,
                        permissions={
                            ADMIN_GUILD: [
                                create_permission(
                                id=140149964020908032,  # owner
                                id_type=SlashCommandPermissionType.USER,
                                permission=True
                                )
                            ]
                        },
                        options=[
                            create_option(
                                name='module',
                                description='name of the module',
                                required=True,
                                option_type=SlashCommandOptionType.STRING,
                            )
                        ])
    async def reload_module(self, ctx, module):
        await ctx.defer(hidden=True)  # reload may take a while

        try:
            self.client.reload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}', hidden=True)
        else:
            await ctx.send('\N{OK HAND SIGN}', hidden=True)
            print(f'Reloaded Module: {module}')


def setup(client):
    client.add_cog(AdminModule(client))