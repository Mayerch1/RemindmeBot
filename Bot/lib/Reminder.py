from datetime import datetime

class Reminder:

    def __init__(self, json = {}):
        if not json:
            json = {}

        self.msg = json.get('msg', None)

        g_id = json.get('g_id', None)
        self.g_id = int(g_id) if g_id else None

        ch_id = json.get('ch_id', None)
        self.ch_id = int(ch_id) if ch_id else None


        target = json.get('target', None)
        self.target = int(target) if target else None


        author = json.get('author', None)
        self.author = int(author) if author else None


        self.at = json.get('at', None)
        if self.at:
            self.at = datetime.fromtimestamp(self.at)


    def __eq__(self, other):
        return self.at == other.at

    def __lt__(self, other):
        return self.at < other.at

    def __le__(self, other):
        return self.at <= other.at

    def __gt__(self, other):
        return self.at > other.at

    def __ge__(self, other):
        return self.at >= other.at

    def __ne__(self, other):
        return self.at != other.at


    def _to_json(self):
        d = dict()


        d['msg'] = self.msg

        d['g_id'] = str(self.g_id) if self.g_id else None
        d['ch_id'] = str(self.ch_id) if self.ch_id else None
        d['target'] = str(self.target) if self.target else None
        d['author'] = str(self.author) if self.author else None
        

        if self.at:
            d['at'] = datetime.timestamp(self.at)

        return d