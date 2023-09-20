from typing import Union
import discord

from util.consts import Consts
from lib.Connector import Connector
from lib.Analytics import Analytics, Types
from lib.CommunitySettings import CommunitySettings, CommunityAction

def check_user_permission(guild_id: int, user_roles: list, required_perms:CommunitySettings=None, active_settings:CommunitySettings=None) -> bool:
    """check if the user holds the required community privilegeds

    Args:
        guild_id (int): _description_
        user_roles (list): guild roles of the user
        required_perms (CommunitySettings, optional): required permissions. Default only checks for Mod-only mode.
        active_settings (CommunitySettings, optional): current settings, is fetched from DB if None

    Returns:
        bool: True if user has permissions, False if permissions are denied
    """

    # if comm mode is disabled, all settings/mods are ignored
    community_mode = Connector.get_community_mode(guild_id)
    if community_mode == Connector.CommunityMode.DISABLED:
        return True
    
    # moderators can do everything
    is_mod = Connector.is_moderator(user_roles)
    if is_mod:
        return True


    if required_perms is None:
        required_perms = CommunityAction() # relaxed permissions, assume no permissions required

    if not active_settings:
        active_settings = Connector.get_community_settings(guild_id)
    
    # at this point the user has no mod permissions
    if active_settings.mods_only or\
        (required_perms.repeating and active_settings.restrict_repeating) or\
        (required_perms.everyone and active_settings.restrict_everyone) or\
        (required_perms.foreign and active_settings.restrict_foreign) or\
        (required_perms.settings):

        Analytics.command_denied()
        return False
    else:
        return True


def get_missing_permissions_embed(guild_id: int, user_roles: list, required_perms:CommunitySettings=None, user_name:str=None) -> discord.Embed:
    
    settings = Connector.get_community_settings(guild_id)

    if check_user_permission(guild_id, user_roles, required_perms, settings):
        return None

    else:       
        if (settings.mods_only):
            missing_perms = 'The bot is set to moderator-only mode\n'
        else:
            missing_perms = 'You do not have permissions to\n'
            if (required_perms.repeating and settings.restrict_repeating):
                missing_perms += '• Repeating Reminders\n'
            if (required_perms.everyone and settings.restrict_everyone):
                missing_perms += '• Mention Everyone\n'
            if (required_perms.foreign and settings.restrict_foreign):
                missing_perms += '• Remind other users\n'
            if required_perms.settings:
                missing_perms += '• Change Bot Settings\n'
            
        
        eb = discord.Embed(title='Missing Permissions',
                           description=f'{missing_perms}'\
                                        '\n'\
                                        'If you think you should be able to perform this command,\n'\
                                        'ask an admin to edit the moderator roles or change the community mode.\n'\
                                        '\n'\
                                        'This can be done with `/settings menu`')
        eb.color = Consts.col_err
        if user_name is not None:
            eb.set_footer(text=f'Issued for {user_name}')
        return eb