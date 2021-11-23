import os
import discord
from discord.ext import commands, tasks

import requests
import json

from lib.Analytics import Analytics


class BotListService:
    def __init__(self, name, api_base, api_path, server_cnt_name=None, shard_cnt_name=None, shard_id_name=None):
        self.name = name
        self.api_base = api_base
        self.api_path = api_path
        
        self.server_cnt_name = server_cnt_name
        self.shard_cnt_name = shard_cnt_name
        self.shard_id_name = shard_id_name

        self.token = None


ServerList = [
    BotListService(
        name='TopGG',
        api_base='https://top.gg/api',
        api_path='/bots/{:d}/stats',
        server_cnt_name='server_count',
        shard_cnt_name='shard_count',
        shard_id_name='shard_id'
    ),
    BotListService(
        name='BotsGG',
        api_base='https://discord.bots.gg/api/v1',
        api_path='/bots/{:d}/stats',
        server_cnt_name='guildCount',
        shard_cnt_name='shardCount',
        shard_id_name='shardId'
    ),
    BotListService(
        name='DBL',
        api_base='https://discordbotlist.com/api/v1',
        api_path='/bots/{:d}/stats',
        server_cnt_name='guilds',
        shard_id_name='shard_id'
    ),
    BotListService(
        name='Discords',
        api_base='https://discords.com/bots/api',
        api_path='/bot/{:d}',
        server_cnt_name='server_count'
    ),
    BotListService(
        name='Disforge',
        api_base='https://disforge.com/api',
        api_path='/botstats/{:d}',
        server_cnt_name='servers'
    ),
    BotListService(
        name='DLSpace',
        api_base='https://api.discordlist.space/v2',
        api_path='/bots/{:d}',
        server_cnt_name='serverCount'
    ),
]


class ServerCountPost(commands.Cog):

    def __init__(self, client):
        BotDir = os.getenv('BOT_ROOT_PREFIX')

        self.client = client
        self.serverList = ServerList
        self.user_agent = "remindMeBot (https://github.com/Mayerch1/RemindmeBot)"

        # init all server objects
        for sList in self.serverList:
            if os.path.exists(f'{BotDir}tokens/{sList.name}.txt'):
                sList.token = open(f'{BotDir}tokens/{sList.name}.txt', 'r').readline()[:-1]
                print(f'starting {sList.name} job')
            else:
                print(f'ignoring {sList.name}, no Token')

        self.update_stats.start()


    def cog_unload(self):
        print('stopping all ServerPost jobs')
        self.update_stats.cancel()


    @commands.Cog.listener()
    async def on_ready(self):
        print('ServerCountPost loaded')



    async def post_count(self, service: BotListService, payload):
        """post the payload to the given service
           token MUST be set in service

        Args:
            service (BotListService): [description]
            payload ([type]): [description]
        """

        url = service.api_base + service.api_path.format(self.client.user.id)
        
        headers = {
            'User-Agent'   : self.user_agent,
            'Content-Type' : 'application/json',
            'Authorization': service.token
        }

        payload = json.dumps(payload)

        r = requests.post(url, data=payload, headers=headers, timeout=5)

        if r.status_code >= 300:
            print(f'{service.name} Server Count Post failed with {r.status_code}')


    @tasks.loop(minutes=30)
    async def update_stats(self):
        """This function runs every 30 minutes to automatically update your server count."""

        server_count = len(self.client.guilds)
        Analytics.guild_cnt(server_count)

        for sList in self.serverList:
            
            if not sList.token:
                continue
            
            cnt_name = sList.server_cnt_name
            shard_name = sList.shard_cnt_name
            id_name = sList.shard_id_name

            payload = {
                f'{cnt_name}': server_count
            }
            if self.client.shard_count and shard_name:
                payload[shard_name] = self.client.shard_count
            if self.client.shard_id and id_name:
                payload[id_name] = self.client.shard_id

            await self.post_count(sList, payload=payload)


    @update_stats.before_loop
    async def update_stats_before(self):
        await self.client.wait_until_ready()


def setup(client):
    client.add_cog(ServerCountPost(client))
