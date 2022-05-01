import os
import logging
import traceback

import discord
from discord.commands import permissions
from discord.ext import commands


ADMIN_GUILD = int(os.getenv('ADMIN_GUILD'))


log = logging.getLogger('Remindme.Admin')

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
        log.info('loaded')
        
    # =====================
    # commands functions
    # =====================
    
    # remove admin commands until permissions v2 is implemented
    # TODO: implemented once lib support was added
    # @commands.slash_command(name='load', description='Load a newly added Cog', guild_ids=[ADMIN_GUILD], default_permission=False)
    # @permissions.is_user(140149964020908032)
    # async def load_module(self, 
    #                         ctx: discord.ApplicationContext, 
    #                         module: discord.Option(str, 'name of the module', required=True)):

    #     await ctx.defer(ephemeral=True)  # reload may take a while
        
    #     try:
    #         self.client.load_extension(module)
    #     except discord.errors.ExtensionError as e:
    #         ex_str = traceback.format_exc()
    #         log.error(ex_str)
    #         await ctx.respond(f'{e.__class__.__name__}: {e}', ephemeral=True)
    #     else:
    #         await ctx.respond('\N{OK HAND SIGN}', ephemeral=True)
    #         log.info(f'Loaded Module: {module}')


    # @commands.slash_command(name='reload', description='Load a newly added Cog', guild_ids=[ADMIN_GUILD], default_permission=False)
    # @permissions.is_user(140149964020908032)
    # async def reload_module(self, 
    #                         ctx: discord.ApplicationContext, 
    #                         module: discord.Option(str, 'name of the module', required=True)):

    #     await ctx.defer(ephemeral=True)  # reload may take a while

    #     try:
    #         self.client.reload_extension(module)
    #     except discord.errors.ExtensionError as e:
    #         ex_str = traceback.format_exc()
    #         log.error(ex_str)
    #         await ctx.respond(f'{e.__class__.__name__}: {e}', ephemeral=True)
    #     else:
    #         await ctx.respond('\N{OK HAND SIGN}', ephemeral=True)
    #         log.info(f'Reloaded Module: {module}')


def setup(client):
    client.add_cog(AdminModule(client))