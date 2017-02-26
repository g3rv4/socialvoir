from celery import Celery
from twython import Twython, TwythonAuthError
import os
import redis
import re

redis_db = redis.StrictRedis(db=2)
app = Celery('tasks', broker=os.environ['CELERY_BROKER'])
app.conf.CELERY_ACCEPT_CONTENT = ['json']
app.conf.CELERY_TASK_SERIALIZER = 'json'

own_twitter = Twython(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'],
                      os.environ['OWN_TOKEN'], os.environ['OWN_SECRET'])


@app.task
def process_tweet(data):
    match = re.search(' ((voir)|(stop)|(unvoir)) @[a-zA-Z0-9_]+$', data['text'])
    if match:
        user_data = get_user_data(data)
        try:
            if user_data:
                twitter = Twython(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'],
                                  user_data['token'], user_data['secret'])

                action = match.group(1)
                target = data['entities']['user_mentions'][-1]

                # get the list
                next_cursor = None
                while True:
                    lists = twitter.show_owned_lists(cursor=next_cursor)
                    dest_list = next((l for l in lists['lists'] if re.search(' %s$' % target['id_str'], l['description'])), None)
                    if dest_list or lists['next_cursor_str'] == '0':
                        break
                    next_cursor = lists['next_cursor_str']

                if action == 'voir':
                    if dest_list is None:
                        dest_list = twitter.create_list(name='voir-%s' % target['screen_name'],
                                                        description='List created by @SocialVoir to follow account %s' % target['id_str'])
                        reply(data, 'list created here: https://twitter.com/%s adding members to it now!' % dest_list['uri'])
                    else:
                        reply(data, "updating the list... if you see no new members, try later... you may be subject to "
                                    "this beautiful twitter secret limit https://gmc.uy/secret-limit")
                    update_list(twitter, dest_list)
                elif action in ('stop', 'unvoir'):
                    if dest_list is not None:
                        twitter.delete_list(list_id=dest_list['id_str'])
                        reply(data, 'alright, that list should be gone now')
                else:
                    reply(data, 'invalid action, visit https://voir.social for details')
        except TwythonAuthError:
            reply(data, "it seems like your authorization tokens no longer work. Visit https://voir.social to fix that")


@app.task
def process_members(token, secret, list, ids, funcname):
    if not ids:
        return

    next_batch = []
    if len(ids) > 10:
        next_batch = ids[10:]
        ids = ids[0:10]

    twitter = Twython(os.environ['TWITTER_API_KEY'], os.environ['TWITTER_API_SECRET'],
                      token, secret)
    getattr(twitter, funcname)(list_id=list, user_id=','.join(ids))

    if next_batch:
        process_members.apply_async(args=(token, secret, list, next_batch, funcname), countdoun=1)


def reply(data, message):
    own_twitter.update_status(
        status="@%s %s" % (data['user']['screen_name'], message), in_reply_to_status_id=data['id_str'])


def get_user_data(data):
    user_data = redis_db.get('user:%s' % data['user']['id_str'])

    if not user_data:
        reply(data, "I don't think we have met yet, visit https://voir.social so that we can be friends")
        return None

    parts = user_data.split(',')
    return {'token': parts[0], 'secret': parts[1]}


def update_list(twitter, dest_list):
    match = re.search(' ([0-9]+)$', dest_list['description'])
    if match:
        target = match.group(1)
        current_ids = twitter.get_friends_ids(user_id=target, stringify_ids=True, count=5000)['ids']

        users_on_list = twitter.get_list_members(list_id=dest_list['id_str'], count=5000, include_entities=False,
                                                 skip_status=True)
        users_on_list = [u['id_str'] for u in users_on_list['users']]

        users_to_add = [u for u in current_ids if u not in users_on_list]
        users_to_remove = [u for u in users_on_list if u not in current_ids]

        process_members.delay(twitter.oauth_token, twitter.oauth_token_secret, dest_list['id_str'], users_to_add, 'create_list_members')
        process_members.delay(twitter.oauth_token, twitter.oauth_token_secret, dest_list['id_str'], users_to_remove, 'delete_list_members')
