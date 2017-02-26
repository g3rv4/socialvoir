from twython import TwythonStreamer
import os
import tasks


class MentionsHandler(TwythonStreamer):
    def on_success(self, data):
        # only do stuff if it's not a retweet
        if 'retweeted_status' not in data:
            tasks.process_tweet.delay(data)

    def on_error(self, status_code, data):
        print data
        print status_code


stream = MentionsHandler(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'],
                         os.environ['OWN_TOKEN'], os.environ['OWN_SECRET'])

stream.statuses.filter(track='@socialvoir')
