class CommunitySettings():
        def __init__(self, json=None):
            
            if json is None:
                json = {}
            
            self.mods_only = json.get('mods_only', False)
            self.restrict_repeating = json.get('restrict_repeating', False)
            self.restrict_everyone = json.get('restrict_everyone', True)
            self.restrict_foreign = json.get('restrict_foreign', False)
            
            
        def _to_json(self):
            return {
                'mods_only': self.mods_only,
                'restrict_repeating': self.restrict_repeating,
                'restrict_everyone': self.restrict_everyone,
                'restrict_foreign': self.restrict_foreign
            }
            
            
        @classmethod
        def full_restricted(cls):
            """restrict the settings to the highest level
               the bot can only be used by moderators
            """
            
            obj = cls()            
            obj.mods_only = True
            obj.restrict_repeating = True
            obj.restrict_everyone = True
            obj.restrict_foreign = True
            
            return obj
        
        @classmethod
        def relaxed(cls):
            """used if community mode is enabled
               but users are allowed to do everything
               
               can be used to pass for permission check
               for any "base" command
            """
            
            obj = cls()
            obj.mods_only = False
            obj.restrict_repeating = False
            obj.restrict_everyone = False
            obj.restrict_foreign = False
            
            return obj
        
        
class CommunityAction():
    def __init__(self, repeating=False, everyone=False, foreign=False, settings=False):
            
        self.repeating = repeating
        self.everyone = everyone
        self.foreign = foreign
        self.settings = settings