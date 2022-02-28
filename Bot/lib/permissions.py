from typing import Union

from lib.Connector import Connector
from lib.Analytics import Analytics, Types
from lib.CommunitySettings import CommunitySettings, CommunityAction

def check_user_permission(guild_id: int, user_roles: list, required_perms:CommunitySettings=None):

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
    settings = Connector.get_community_settings(guild_id)
    
    # at this point the user has no mod permissions
    if settings.mods_only or\
        (required_perms.repeating and settings.restrict_repeating) or\
        (required_perms.everyone and settings.restrict_everyone) or\
        (required_perms.foreign and settings.restrict_foreign) or\
        (required_perms.settings):

        return False
        Analytics.command_denied()
    else:
        return True