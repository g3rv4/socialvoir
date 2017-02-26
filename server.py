from flask import Flask, session, redirect, request
from flask_session import Session
from twython import Twython
import os
import redis

app = Flask(__name__)
redis_db = redis.StrictRedis(db=2)

SESSION_TYPE = 'redis'
SESSION_REDIS = redis_db
SESSION_USE_SIGNER = True
PERMANENT_SESSION_LIFETIME = 120
Flask.secret_key = os.environ['SECRET_KEY']

app.config.from_object(__name__)
Session(app)


@app.route("/")
def go_to_twitter():
    twitter = Twython(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'])
    auth = twitter.get_authentication_tokens(callback_url='%s/twitter-callback' % os.environ['CALLBACK_HOST'])

    session['oauth_token'] = auth['oauth_token']
    session['oauth_token_secret'] = auth['oauth_token_secret']

    return redirect(auth['auth_url'])


@app.route("/twitter-callback")
def twitter_callback():
    twitter = Twython(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'],
                      session['oauth_token'], session['oauth_token_secret'])

    final_step = twitter.get_authorized_tokens(request.args.get('oauth_verifier'))

    redis_db.set('user:%s' % final_step['user_id'], '%s,%s' % (final_step['oauth_token'], final_step['oauth_token_secret']))

    return '<html><head><title>@SocialVoir</title><meta http-equiv="refresh" content="3;url=https://voir.social" /></head><body>you are all set! redirecting you to <a href="https://voir.social">voir.social</a></body></html>'

if __name__ == "__main__":
    app.run()
