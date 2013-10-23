import soundcloud


class SoundCloud:
    def __init__(self):
        self.client = soundcloud.Client(client_id="fddd281b41e49cbfef36d3319532ac9c")

    def client(self):
        return self.client

    def tracks(self, search):
        return self.client.get('/tracks', limit=15, q=search, filter="streamable")

    def user(self, id):
        return self.client.get('/users/%s' % id)


