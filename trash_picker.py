#!/usr/bin/python

import sys
import string

# python-twitter module
import twitter

# for pycurl stuff
import pycurl, json, urllib, StringIO


# file to contain auth config settings:
AUTH_CONFIG_FILE = '.twit_auth'


#TODO: accept this from command line or config file
USERS_TO_FOLLOW = [
    'mr_sdflow',
    '_jasonp_'
]


#
# example of regular tweet in JSON
# {"in_reply_to_user_id":null,"text":"dude","entities":{"urls":[],"hashtags":[],"user_mentions":[]},"coordinates":null,"created_at":"Wed Jul 13 00:48:49 +0000 2011","id_str":"90945744802033664","place":null,"source":"web","favorited":false,"in_reply_to_status_id_str":null,"geo":null,"in_reply_to_screen_name":null,"truncated":false,"in_reply_to_user_id_str":null,"contributors":null,"user":{"follow_request_sent":null,"profile_background_tile":false,"default_profile":true,"lang":"en","notifications":null,"created_at":"Tue Jan 11 06:46:55 +0000 2011","id_str":"236724113","contributors_enabled":false,"statuses_count":1,"profile_link_color":"0084B4","is_translator":false,"profile_background_image_url_https":"https:\/\/si0.twimg.com\/images\/themes\/theme1\/bg.png","profile_sidebar_border_color":"C0DEED","profile_image_url":"http:\/\/a2.twimg.com\/sticky\/default_profile_images\/default_profile_3_normal.png","description":null,"listed_count":0,"following":null,"verified":false,"time_zone":"Pacific Time (US & Canada)","favourites_count":1,"friends_count":0,"profile_use_background_image":true,"screen_name":"mr_sdflow","profile_background_color":"C0DEED","followers_count":0,"url":null,"profile_image_url_https":"https:\/\/si0.twimg.com\/sticky\/default_profile_images\/default_profile_3_normal.png","profile_background_image_url":"http:\/\/a0.twimg.com\/images\/themes\/theme1\/bg.png","protected":false,"default_profile_image":true,"name":"SDFlow.org","profile_text_color":"333333","location":null,"id":236724113,"show_all_inline_media":false,"geo_enabled":false,"utc_offset":-28800,"profile_sidebar_fill_color":"DDEEF6"},"retweeted":false,"retweet_count":0,"id":90945744802033664,"in_reply_to_status_id":null}
#
#
# example of a delete
# {"delete":{"status":{"user_id_str":"236724113","id_str":"90945744802033664","id":90945744802033664,"user_id":236724113}}}
#

#########################################

# func to read in an auth config file of user/pass, consumer and access tokens and keys 
def read_config(config_file):
    #XXX: kind of crude but it works
    config = {}
    f = None
    try:
        f = open(config_file)
        for l in f:
            if ':' not in l:
                continue
            k, v = l.split(':')
            k = k.lower().strip()
            v = v.strip()
            config[k] = v
    except Exception as e:
        print 'CONFIG ERROR: %s: %s' % (config_file, e)
        return None # returning None signifies error
    finally:
        if f is not None:
            f.close()
    return config


# class to use pycurl for streaming API
class PycurlClient:
    STREAM_URL = 'http://stream.twitter.com/1/'
    REST_URL = 'http://api.twitter.com/1/'

    def __init__(self):
       self.buffer = ''
       self.username = None
       self.password = None
       self.tweet_cache = {}
       self.conn = pycurl.Curl()

    def set_userpass(self, username, password):
        self.username = username
        self.password = password


    def stream_connect(self, api, args = None):
        url = PycurlClient.STREAM_URL + api
        if args:
            url += '?%s' % ( urllib.urlencode(args) )
        print 'Set Streaming API URL: %s' % (url)
        self.conn.setopt(pycurl.URL, url)

        if self.username and self.password:
            self.conn.setopt(pycurl.USERPWD, '%s:%s' % (self.username, self.password))

        # args are all done as POST body
        if args:
            data = urllib.urlencode(args)
            self.conn.setopt(pycurl.POSTFIELDS, data)

        self.conn.setopt(pycurl.WRITEFUNCTION, self.on_receive)
        self.conn.perform()


    def on_receive(self, data):
        # add data received to buffer
        self.buffer += data

        # if not end of line yet, or only whitespace just return -- nothing to do yet
        if not data.endswith('\r\n') or len(self.buffer.strip()) == 0:
            return

        # parse JSON in buffer, then clear for next read
        content = json.loads(self.buffer)
        self.buffer = ''

        self.process_content(content)


    def process_content(self, tweet):
        # figure out what kind of tweet it is and then act accordingly
        if tweet.get('text') and tweet.get('id'):
            # STANDARD TWEET - save indexed by user ID and tweet ID
            user_id = tweet['user']['id']
            user_name = tweet['user']['screen_name']
            tweet_id = tweet['id']
            tweet_text = tweet['text']
            if user_id not in self.tweet_cache:
                self.tweet_cache[user_id] = {}
            self.tweet_cache[user_id][tweet_id] = tweet
            print '@%s tweeted (user ID=%d, tweet ID=%d)' % (user_name, user_id, tweet_id)
            print '%s\n' % (tweet_text)

        elif 'delete' in tweet:
            # USER DELETED A TWEET...
            user_id = tweet['delete']['status']['user_id']
            tweet_id = tweet['delete']['status']['id']
            print 'User %d deleted a tweet! (tweet id=%d)' % (user_id, tweet_id)

            # see if we've saved this one, if so then retweet the text
            if user_id not in self.tweet_cache or tweet_id not in self.tweet_cache[user_id]:
                print 'Sorry that tweet not saved yet... no retweet possible'
            else:
                # RETWEET IT FOR THE WORLD TO SEE
                print 'We have that tweet saved!'
                dt = self.tweet_cache[user_id][tweet_id]
                print 'DELETED TWEET by @%s:\n%s' % (dt['user']['screen_name'], dt['text'])
        else:
            print 'Got some other kind of mystery tweet event??\n', tweet, '\n'



#################################################################################
# MAIN
#########################################

if __name__ == '__main__':

    # READ CONFIG
    auth_config = read_config(AUTH_CONFIG_FILE)
    if auth_config is None:
        print 'Unable to read auth config file... exitting'
        raise SystemExit()
    for f in [ 'user', 'password', 'consumer_key', 'consumer_secret', 'access_key', 'access_secret' ]:
        if f not in auth_config:
            print '"%s" missing from auth config: %s' % (f, AUTH_CONFIG_FILE)
            raise SystemExit(1)

    # AUTH and SETUP
    api = twitter.Api(consumer_key = auth_config['consumer_key'],
                      consumer_secret = auth_config['consumer_secret'],
                      access_token_key = auth_config['access_key'],
                      access_token_secret = auth_config['access_secret'])
    users_by_name = {}
    try:
        for user in api.UsersLookup(screen_name = USERS_TO_FOLLOW):
            users_by_name[user.screen_name] = user.id
    except Exception as e:
        print 'Got exception doing users/lookup: ', e
        raise SystemExit(1)

    # put together args for "filter" stream, i.e. a comma separated list of followed user IDs
    follow_arg = ','.join(str(u) for u in users_by_name.values())

    # use python-twitter REST API to get user IDs to follow based on screen names
    # this returns a dict of screen name to user ID mappings
    # print out users to be followed
    print '\nFollowing these users:'
    for k, v in users_by_name.items():
        print '\t%-16s (user ID = %s)' % (k, str(v))
    print

    #####
    # PROCESS STREAM

    client = PycurlClient()
    client.set_userpass(auth_config['user'], auth_config['password'])
    print 'Connecting to twitter stream...'
    try:
        client.stream_connect('statuses/filter.json', dict(follow = follow_arg))
    except Exception as e:
        print 'Got exception doing stream_connect(): ', e
    print 'Done.'



