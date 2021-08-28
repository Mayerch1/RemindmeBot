import os
import discord
from discord.ext import commands, tasks

import requests
import json

from lib.Analytics import Analytics


class Disforge(commands.Cog):

    def __init__(self, client):
        BotDir = os.getenv('BOT_ROOT_PREFIX')
        
        self.BASE = 'https://disforge.com/api'
        self.user_agent = "remindMeBot (https://github.com/Mayerch1/RemindmeBot)"

        if os.path.exists(f'{BotDir}tokens/disforge.txt'):
            self.client = client
            self.token = open(f'{BotDir}tokens/disforge.txt', 'r').readline()[:-1]

            print('starting Disforge job')
            self.update_stats.start()

        else:
            print('ignoring Disforge, no Token')
        

    def cog_unload(self):
        print('stopping Disforge job')
        self.update_stats.cancel()


    async def post_count(self, url, payload):
        if not self.token:
            print('no Disforge Token')
            return

        url = self.BASE + url
        
        headers = {
            'User-Agent'   : self.user_agent,
            'Content-Type' : 'application/json',
            'Authorization': self.token
        }

        payload = json.dumps(payload)

        r = requests.post(url, data=payload, headers=headers)

        if r.status_code >= 300:
            print(f'Disforge Server Count Post failed with {r.status_code}')


    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""

        server_count = len(self.client.guilds)
        Analytics.guild_cnt(server_count)

        payload = {
            'servers': server_count
        }

        await self.post_count( f'/botstats/{self.client.user.id}', payload=payload)


    @update_stats.before_loop
    async def update_stats_before(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(Disforge(client))
