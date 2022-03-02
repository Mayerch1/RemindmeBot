import discord
from enum import Enum


class VerboseErrors:

    @staticmethod
    def _perm_to_readable(perm: str):
        perm = perm.replace('_', ' ').title()
        return perm

    @staticmethod
    def _get_embed(cmd_name, permissions: list, additional_info):
        embed = discord.Embed(title='Missing Permission(s)',
                                description="I need more permissions to perform this command", colour=0xff0000)

        if cmd_name:
            embed.add_field(name='Command Name', value=cmd_name, inline=True)

        if additional_info:
            embed.add_field(name='Note', value=additional_info, inline=True)

        for perm in permissions:
            perm_str = VerboseErrors._perm_to_readable(perm)
            embed.add_field(name='Missing', value=perm_str, inline=False)

        return embed

    @staticmethod
    async def forbidden(cmd_name: str, permissions: discord.Permissions, channel, additional_info=None):

        if permissions:
            # convert missing permissions into list with names
            perms_extract = list(filter(lambda perm: perm[1], list(permissions))) # all attributes with value True
            perms_list = list(map(lambda perm: perm[0], perms_extract)) # only keep names, as filtered for True
        else: 
            perms_list = [] # allows to only send 'aditional_info

        embed = VerboseErrors._get_embed(
                cmd_name, perms_list, additional_info)

        # even the 'embed' permission might be missing
        try:
            if isinstance(channel, discord.ApplicationContext):
                await channel.respond(embed=embed)
            else:
                await channel.send(embed=embed)
        except discord.errors.Forbidden:

            err_str = 'I need following permissions to perform this action: '

            # check if perm is enum or str
            if not perms_list or 'embed_links' not in perms_list:
                # this catch block in only entered when this is missing
                perms_list.append('embed_links')
                
            perms_strs = list(map(lambda perm: VerboseErrors._perm_to_readable(perm), perms_list))

            err_str += '"' # opening "
            err_str += '", "'.join(perms_strs)
            err_str += '"' # closing "
            await channel.send(err_str)


    @staticmethod
    def _get_effective_permission(granted_perms: discord.Permissions, channel: discord.TextChannel, channel_overwrite, me_override = None):
        # check for overrides by 'channel'
        if channel_overwrite:
            # the list holds lowest permission at first index
            # apply channel-role from low-high onto the granted permissions
            # result after iteration is effective permissions for that channel
            if me_override:
                me = me_override
            else:
                me = channel.guild.me
            granted_perms = channel.permissions_for(me)

        return granted_perms


    @staticmethod
    def get_manage_messages_perms():
        """get Permissions obj for managing messages

        Returns:
            [discord.Permissions]: has enough Perms for menage_messages
        """
        return discord.Permissions(manage_messages=True, read_messages=True)

    @staticmethod
    def can_manage_messages(channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, user_override = None):
        """shortcut for has_permissions with manage_messages

        Args:
            channel (discord.TextChannel): channel for overwrite, supplies guild and channel permissions
            channel_overwrite (bool, optional): apply channel overwrite (for bot user). Defaults to True.
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)

        Returns:
            [type]: true, if requested permissions are granted
        """

        return VerboseErrors.has_permission(VerboseErrors.get_manage_messages_perms(), 
                    channel = channel, 
                    channel_overwrite= channel_overwrite, 
                    granted_perms = granted_perms,
                    user_override=user_override)



    @staticmethod
    def get_send_messages_perms():
        """get Permissions obj for send_messages

        Returns:
            [discord.Permissions]: has enough Perms for send_messages
        """
        return discord.Permissions(send_messages=True, read_messages=True)

    @staticmethod
    def can_send_messages(channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, user_override = None):
        """shortcut for has_permissions with send_messages

        Args:
            channel (discord.TextChannel): channel for overwrite, supplies guild and channel permissions
            channel_overwrite (bool, optional): apply channel overwrite (for bot user). Defaults to True.
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)

        Returns:
            [type]: true, if requested permissions are granted
        """
        return VerboseErrors.has_permission(VerboseErrors.get_send_messages_perms(), 
                    channel = channel, 
                    channel_overwrite= channel_overwrite, 
                    granted_perms = granted_perms,
                    user_override=user_override)

    @staticmethod
    def get_embed_perms():
        """get Permissions obj for embed_links

        Returns:
            [discord.Permissions]: has enough Perms for embed_links
        """
        return discord.Permissions(embed_links=True, send_messages=True, read_messages=True)

    @staticmethod
    def can_embed(channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, user_override = None):
        """shortcut for has_permissions with embed_links

        Args:
            channel (discord.TextChannel): channel for overwrite, supplies guild and channel permissions
            channel_overwrite (bool, optional): apply channel overwrite (for bot user). Defaults to True.
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)

        Returns:
            [type]: true, if requested permissions are granted
        """

        return VerboseErrors.has_permission(VerboseErrors.get_embed_perms(), 
                    channel = channel, 
                    channel_overwrite= channel_overwrite, 
                    granted_perms = granted_perms,
                    user_override=user_override)


    @staticmethod
    def get_react_perms():
        """get Permissions obj for reaction to messages

        Returns:
            [discord.Permissions]: has enough Perms for reaction to messages
        """
        return discord.Permissions(add_reactions=True, read_message_history=True, read_messages=True)

    @staticmethod
    def can_react(channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, user_override=None):
        """shortcut for has_permission with add_reactions an read_message_history

        Args:
            channel (discord.TextChannel): channel for overwrite, supplies guild and channel permissions
            channel_overwrite (bool, optional): apply channel overwrite (for bot user). Defaults to True.
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)

        Returns:
            [type]: true, if requested permissions are granted
        """

        return VerboseErrors.has_permission(VerboseErrors.get_react_perms(), 
                    channel = channel, 
                    channel_overwrite= channel_overwrite, 
                    granted_perms = granted_perms,
                    user_override=user_override)


    @staticmethod
    def has_permission(wanted_perms: discord.Permissions, channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, user_override = None):
        """determin if bot has requested permissions (in a specific channel)

        Args:
            wanted_perms (discord.Permissions): requested permission
            channel (discord.TextChannel): channel for overwrite, supplies guild and channel permissions
            channel_overwrite (bool, optional): apply channel overwrite (for bot user). Defaults to True.
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)

        Returns:
            [type]: true, if requested permissions are granted
        """

        if not granted_perms:
            granted_perms = channel.guild.me.guild_permissions

        effective = VerboseErrors._get_effective_permission(granted_perms, channel, channel_overwrite, me_override=user_override)

        return (wanted_perms <= effective) or effective.administrator


    @staticmethod
    async def show_missing_perms(cmd_name: str, wanted_perms: discord.Permissions, channel: discord.TextChannel, channel_overwrite = True, granted_perms: discord.Permissions = None, additional_info = None, text_alternative = None, user_override = None):
        """check if wanted_perms are granted, show error message in chat if not
            checks for overrides in channels aswell

        Args:
            cmd_name (str): shown in error message
            wanted_perms (discord.Permissions): requested bot permissions
            channel (discord.TextChannel): evaluate for this channel, send error message aswell, as long as text_alternative is not set
            channel_overwrite (bool): specify if channel permission overrides should be applied
            granted_perms (discord.Permissions): override guild permissions of 'channel' of not None. Defaults to None
            additional_info (str): show this as extra field in case of error. Defaults to None
            text_alternative (str): output to this channel instead of the 'channel' arg
            user_override (discord.Member): evaluate permissions for the given user, not for the bot. Defaults to None (=Bot)
            

        Returns:
            [bool]: True if alll premissions are present, false else
        """

        if not granted_perms:
            granted_perms = channel.guild.me.guild_permissions

        granted = VerboseErrors._get_effective_permission(granted_perms, channel, channel_overwrite, me_override=user_override)

        # all wanted perms are included in granted perms
        # no need for error message
        if (wanted_perms <= granted_perms):
            return True
        elif granted.administrator:
            return True # admin can do everything
        

        # create an object with all missing permissions
        missing_val = (wanted_perms.value - (wanted_perms.value & granted.value))
        missing = discord.Permissions(missing_val)

        out_channel = channel

        if text_alternative:
            out_channel = text_alternative

        if not isinstance(out_channel, discord.TextChannel) and\
            not isinstance(out_channel, discord.ApplicationContext):
            # no way to output feedback
            return False

        await VerboseErrors.forbidden(cmd_name, missing, out_channel, additional_info=additional_info)
        return False
