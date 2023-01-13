import spotipy
from spotipy.oauth2 import SpotifyOAuth
from secrets import spotify_user_id, spotify_token, spotify_redirect_uri
from collections import defaultdict
import random


class Main:
    def __init__(self, genre, duration):
        self._user_id = ''
        self._sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=spotify_user_id,
                                                             client_secret=spotify_token,
                                                             redirect_uri=spotify_redirect_uri,
                                                             scope=['user-top-read', 'user-read-private', 'playlist-modify-public']))

        self.genre = genre

        # Optimize depending on the units etc  | Units of the var: ds
        self.expected_duration = duration*60*10
        self.min_t = self.expected_duration - 150
        self.max_t = self.expected_duration + 150

        # Key=track id | Value=importance where 10 is a user track and 1 a recommended track
        self.track_catalog = defaultdict(int)
        self.current_max_time = 0

        # Optimal combination of tracks
        self.playlist = []

    # Get all the available songs that user liked or are its playlists
    def user_tracks(self):
        self._get_user_tracks('short_term', 10)
        if len(self.track_catalog) != 0:
            val, wt = list(zip(*list(self.track_catalog.values())))
            self.playlist = self.compute_optimal_tracks(wt, val, len(wt))

        if self.playlist == []:  # If unable to get an optimal playlist with short_term songs
            self._get_user_tracks('medium_term', 5)
            if len(self.track_catalog) != 0:
                val, wt = list(zip(*list(self.track_catalog.values())))
                self.playlist = self.compute_optimal_tracks(wt, val, len(wt))

        while self.playlist == []:  # If unable to get an optimal playlist with both short and medium_term songs
            self.get_spotify_recommendations()
            val, wt = list(zip(*list(self.track_catalog.values())))
            self.playlist = self.compute_optimal_tracks(wt, val, len(wt))

    # Medium_term = 6 months | Short_term = 4 weeks
    def _get_user_tracks(self, term, lvl):
        results = self._sp.current_user_top_tracks(
            limit=50, offset=0, time_range=term)
        self.__show_tracks(results, lvl)

        i = 0
        while results['next']:
            results = self._sp.current_user_top_tracks(
                limit=50, offset=i+50, time_range=term)
            self.__show_tracks(results, lvl)
            i += 50

    # Adds the given term user's tracks to the track catalog
    def __show_tracks(self, results, lvl):
        for track in results['items']:
            # In order to avoid repeating tracks with different level of importance
            if track['id'] not in self.track_catalog:
                track_genres = self._sp.album(track['album']['uri'])['genres']
                if len(track_genres) == 0:
                    for artist in track['artists']:
                        track_genres += self._sp.artist(
                            artist['uri'])['genres']

                if self.genre in track_genres:
                    time = self._sp.audio_features(tracks=[track['id']])[
                        0]['duration_ms']//100
                    self.track_catalog[track['id']] = (lvl, time)
                    self.current_max_time += time

    def _define_q(self):
        # 3 min is the average time of a track
        q = (self.min_t - self.current_max_time) // (3*60*10)
        if q < 0:
            return 5
        elif q + 5 > 100:
            return 100  # Spotify limit request
        else:
            return q + 5

    # Get a bunch of songs from the same genre recommended by Spotify
    def get_spotify_recommendations(self):
        q = self._define_q()
        if len(self.track_catalog) == 0:
            self.__add_spotify_tracks(self._sp.recommendations(
                seed_genres=[self.genre], limit=q))
        else:
            self.__add_spotify_tracks(self._sp.recommendations(
                seed_tracks=random.sample(list(self.track_catalog.keys()), 5), limit=q))

    def __add_spotify_tracks(self, tracks):
        for track in tracks['tracks']:
            if track['id'] not in self.track_catalog.keys():
                time = self._sp.audio_features(tracks=[track['id']])[
                    0]['duration_ms']//100
                self.track_catalog[track['id']] = (1, time)
                self.current_max_time += time

    # Takes self.track_catalog and calculates the optimal mix, return an empty list if impossible
    def compute_optimal_tracks(self, wt, val, n):
        if self.current_max_time < self.min_t:
            return []

        K = [[0 for w in range(self.max_t + 1)]
             for i in range(n + 1)]

        # Build table K[][] in bottom
        # up manner
        for i in range(n + 1):
            for w in range(self.max_t + 1):
                if i == 0 or w == 0:
                    K[i][w] = 0
                elif wt[i - 1] <= w:
                    K[i][w] = max(val[i - 1]
                                  + K[i - 1][w - wt[i - 1]],
                                  K[i - 1][w])
                else:
                    K[i][w] = K[i - 1][w]

        # stores the result of Knapsack
        res = K[n][self.max_t]

        total = 0
        playlist = []

        w = self.max_t
        for i in range(n, 0, -1):
            if res <= 0:
                break
            # either the result comes from the top (K[i-1][w]) or from (val[i-1]
            # + K[i-1] [w-wt[i-1]]) as in Knapsack table. If it comes from the latter
            # one/ it means the item is included.
            if res == K[i - 1][w]:
                continue
            else:

                # This item is included.
                total += wt[i-1]
                playlist.append(list(self.track_catalog.keys())[i - 1])

                # Since this weight is included
                # its value is deducted
                res = res - val[i - 1]
                w = w - wt[i - 1]

        if total < self.min_t:
            return []
        else:
            return playlist

    def _get_user_id(self):
        self._user_id = self._sp.current_user()['id']

    def create_playlist(self):
        self._get_user_id()
        playlist_id = self._sp.user_playlist_create(
            self._user_id, 'sample_name', public=True, collaborative=False, description='')['id']

        i = 0
        while i*100 < len(self.playlist):
            self._sp.user_playlist_add_tracks(
                self._user_id, playlist_id, self.playlist[i*100:(i+1)*100], position=None)
            i += 1

        return playlist_id, 'sample_name', self.genre, self.expected_duration/600

    def _proves(self):
        print(self.track_catalog)
        print(self.expected_duration)
        print(self.playlist)


if __name__ == '__main__':
    
