import os
import discord
from discord.ext import commands, tasks

import requests
import json

from lib.Analytics import Analytics


class TopGG(commands.Cog):

    def __init__(self, client):
        BotDir = os.getenv('BOT_ROOT_PREFIX')
        
        self.BASE = 'https://top.gg/api'
        self.user_agent = "remindMeBot (https://github.com/Mayerch1/RemindmeBot)"

        if os.path.exists(f'{BotDir}tokens/topGGToken.txt'):
            self.client = client
            self.token = open(f'{BotDir}tokens/topGGToken.txt', 'r').readline()[:-1]

            print('starting topGG job')
            self.update_stats.start()

        else:
            print('ignoring TopGG, no Token')
        

    def cog_unload(self):
        print('stopping topGG job')
        self.update_stats.cancel()


    async def post_count(self, url, payload):
        if not self.token:
            print('no topGG Token')
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
            print(f'TopGG Server Count Post failed with {r.status_code}')


    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""

        server_count = len(self.client.guilds)
        Analytics.guild_cnt(server_count)

        payload = {
            'server_count': server_count
        }
        if self.client.shard_count:
            payload["shard_count"] = self.client.shard_count
        if self.client.shard_id:
            payload["shard_id"] = self.client.shard_id

        await self.post_count( f'/bots/{self.client.user.id}/stats', payload=payload)


    @update_stats.before_loop
    async def update_stats_before(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(TopGG(client))