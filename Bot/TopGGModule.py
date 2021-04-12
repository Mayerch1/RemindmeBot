import os
import discord
from discord.ext import commands, tasks

import requests
import json




class TopGG(commands.Cog):

    def __init__(self, client):
        self.BASE = 'https://top.gg/api'

        self.user_agent = "remindMeBot (https://github.com/Mayerch1/RemindmeBot)"

        if os.path.exists('topGGToken.txt'):
            self.client = client
            self.token = open('topGGToken.txt', 'r').readline()[:-1]

            #self.dblpy = dbl.DBLClient(self.client, self.token, autopost=True)
            #self.dblpy = dbl.DBLClient(self.bot, self.token)
            print('Started topGG server')
            self.update_stats.start()

        else:
            print('Ignoring TopGG, no Token')
        

    def cog_unload(self):
        self.update_stats.cancel()

    

    async def post_count(self, url, payload):
        if not self.token:
            print('no topGGToken')
            return

        url = self.BASE + url
        
        headers = {
            'User-Agent'   : self.user_agent,
            'Content-Type' : 'application/json',
            'Authorization': self.token
        }

        payload = json.dumps(payload)

        r = requests.post(url, data=payload, headers=headers)

        if r.status_code != 200:
            print(f'Server Count Post failed with {r.status_code}: {r.content}')



    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""

        server_count = len(self.client.guilds)

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


