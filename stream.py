from tweepy import API, OAuthHandler, Stream, StreamListener
from time import sleep
import requests
import urllib3
from dotenv import load_dotenv
from threading import Thread
import os
import json
import sqlite3

load_dotenv('.env')

sqlite_file = 'blocker_app.sqlite'

# Go to http://apps.twitter.com and create an app.
# The consumer key and secret will be generated for you after
consumer_key = os.getenv('APP_CONSUMER_KEY')
consumer_secret = os.getenv('APP_CONSUMER_SECRET')
access_token = os.getenv('APP_ACCESS_TOKEN')
access_token_secret = os.getenv('APP_ACCESS_TOKEN_SECRET')
mention = "@TweepBlocker"

auth = OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = API(auth)

auth_url = str(os.getenv('APP_URL'))+'/start'


class StdOutListener(StreamListener):
    """ A listener handles tweets that are received from the stream.
    This is a basic listener that just prints received tweets to stdout.
    """

    def on_data(self, data):
        # Using threads so incoming requests can be attended to simultenously
        Thread(target=handle(data)).start()
        return True

    def on_error(self, status):
        print('Error occurred: ', status)


def handle(data):
    global api, mention, auth_url

    # First we decode the payload
    decoded = json.loads(data)

    # let's grab some data we need
    tweet = decoded['text']
    tweet_id = decoded['id_str']
    handle = decoded['user']['screen_name']
    user_id = decoded['user']['id_str']

    # avoid infinite loop
    if decoded['user']['screen_name'] == mention:
        return

    # if no tweet quoted or can't be found
    if not decoded['in_reply_to_status_id']:
        return

    # if in reply to multiple users https://twitter.com/dara_tobi/status/1213220598018715648
    # if 'entities' in decoded and 'user_mentions' in decoded['entities'] and len(decoded['entities']['user_mentions']) > 1:
    #     return

    # if keyword not included https://twitter.com/theshalvah/status/1213218709403262979
    if 'block' not in str(decoded['text'].replace(mention, '')).lower():
        return
    else:
        tweet_object = api.get_status(decoded['in_reply_to_status_id'])

        if not tweet_object:
            return
        tweet = {
            'id' : tweet_object.id,
            'id_str' : tweet_object.id_str,
            'text' : tweet_object.text,
            'created_at' : tweet_object.created_at,
            'user' : {
                'id' : tweet_object.user.id,
                'id_str' : tweet_object.user.id_str,
                'screen_name' : tweet_object.user.screen_name,
            },
        }

        # If quoted user is the poster user
        if decoded['user']['screen_name'] == tweet['user']['screen_name']:
            return

        # if no oauth
        oauth = fetch_oauth(user_id)
        if not oauth:

            # Tell user to authenticate us, so we can complete his/her request
            text = "Hello @" + handle + ", I noticed you've not given me permission to block on your behalf. Kindly " \
                                        "visit " + auth_url + " to do that and I'll complete the action once that's done."
            save_block(decoded['user'], tweet['user'], tweet, False)
        else:
            # In case blocking failed for whatever reason
            block_for_me(oauth, decoded['user'], tweet['user'], tweet, True)
            text = "Hello @" + handle + ", @" + tweet['user']['screen_name'] + " has been blocked for you."

    # Tweet reply
    api.update_status(text, tweet_id)


def fetch_oauth(user_id):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'oauths'

    connection.execute('SELECT * FROM ' + table_name + ' WHERE id_str=:user_id',
                           {'user_id': user_id})
    oauth = connection.fetchone()
    conn.commit()
    conn.close()

    return {
        'id': oauth[0],
        'screen_name': oauth[1],
        'id_str': oauth[2],
        'real_oauth_token': oauth[3],
        'real_oauth_token_secret': oauth[4],
        'created_at': oauth[5],
    } if oauth else {}


def fetch_oauth_by_username(screen_name):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'oauths'

    connection.execute('SELECT * FROM '+table_name+' WHERE screen_name=:screen_name',
                       {'screen_name':screen_name})

    oauth = connection.fetchone()
    conn.commit()
    conn.close()

    return {
        'id': oauth[0],
        'screen_name': oauth[1],
        'id_str': oauth[2],
        'real_oauth_token': oauth[3],
        'real_oauth_token_secret': oauth[4],
        'created_at': oauth[5],
    } if oauth else {}


def update_oauth(oauth, id):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'oauths'

    query = "UPDATE "+table_name+" SET real_oauth_token = ?, real_oauth_token_secret = ? WHERE id = ?"
    connection.execute(query, (oauth['real_oauth_token'], oauth['real_oauth_token_secret'], id))

    conn.commit()
    conn.close()

    return True


def save_oauth(oauth, user):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'oauths'

    connection.execute("INSERT INTO "+table_name+
                       "(screen_name, id_str, real_oauth_token, real_oauth_token_secret) "
                       "VALUES ( :screen_name, :id_str, :real_oauth_token, :real_oauth_token_secret )",
                       {

        'screen_name':user['screen_name'],
        'id_str':user['id'],
        'real_oauth_token':oauth['real_oauth_token'],
        'real_oauth_token_secret':oauth['real_oauth_token_secret'],
    })

    conn.commit()
    conn.close()

    return True


def validate_oauth(oauth):
    try:
        auth.set_access_token(oauth['real_access_token'], oauth['access_token_secret'])
        api = API(auth)
        api.get_user()
        return True
    except:
        return None


def save_block(user, victim, tweet, completed=True):
    if not isinstance(user, dict):
        user = dict(user)
    if not isinstance(victim, dict):
        victim = dict(victim)
    if not isinstance(tweet, dict):
        tweet = dict(tweet)
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'blocks'

    connection.execute("INSERT INTO  "+table_name+
                           "( user_id, user_screen_name, victim_id, victim_screen_name, tweet_id, tweet_text, tweet_date, completed ) "
                           "VALUES ( "
                           ":user_id, :user_screen_name, :victim_id, :victim_screen_name, :tweet_id, :tweet_text, :tweet_date, :completed"
                           " )"
            , {
            'user_id': user['id'],
            'user_screen_name': user['screen_name'],
            'victim_id': victim['id'],
            'victim_screen_name': victim['screen_name'],
            'tweet_id': tweet['id'],
            'tweet_text': tweet['text'],
            'tweet_date': tweet['created_at'],
            'completed': 1 if completed else 0
    })

    conn.commit()
    conn.close()

    return True


def save_token(secret, token):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'tokens'

    connection.execute("INSERT INTO  "+table_name+
                           "( token, secret ) "
                           "VALUES ( "
                           ":token, :secret"
                           " )"
            , {
            'token': token,
            'secret': secret,
    })

    conn.commit()
    conn.close()

    return True


def fetch_token(token):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'tokens'

    connection.execute("SELECT * FROM  "+table_name+" WHERE token=:token"
            , {
            'token': token,
    })

    token = connection.fetchone()
    conn.commit()
    conn.close()

    return {
        token[1]: token[2],
    } if token else None


def delete_token(token):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'tokens'

    connection.execute("DELETE FROM "+table_name+" WHERE token=:token"
            , {
            'token': token,
    })

    conn.commit()
    conn.close()

    return True


def fetch_block(user_id, victim_id):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'blocks'

    connection.execute(
        'SELECT * FROM '+table_name+' WHERE user_id=:user_id AND victim_id=:victim_id ORDER BY id DESC LIMIT 1',
            {'user_id':user_id, 'victim_id':victim_id})
    block = connection.fetchone()
    conn.commit()
    conn.close()

    return {
        'id': block[0],
        'user_id': block[1],
        'user_screen_name': block[2],
        'victim_id': block[3],
        'victim_screen_name': block[4],
        'tweet_id': block[5],
        'tweet_text': block[6],
        'tweet_date': block[7],
        'completed': block[8],
        'created_at': block[9],
    } if block else {}


def fetch_pending_block(user_id):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'blocks'

    connection.execute(
        'SELECT * FROM '+table_name+' WHERE user_id=:user_id AND completed=0 ORDER BY id DESC LIMIT 1',
        {'user_id':user_id})
    block = connection.fetchone()
    conn.commit()
    conn.close()

    return  {
        'id' : block[0],
        'user_id' : block[1],
        'user_screen_name' : block[2],
        'victim_id' : block[3],
        'victim_screen_name' : block[4],
        'tweet_id' : block[5],
        'tweet_text' : block[6],
        'tweet_date' : block[7],
        'completed' : block[8],
        'created_at' : block[9],
    } if block else {}


def fetch_blocks(username):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'blocks'

    connection.execute(
        'SELECT * FROM '+table_name+' WHERE user_screen_name=:username ORDER BY id',
        {'username':username})
    blocks = connection.fetchall()
    conn.commit()
    conn.close()

    results = []
    if blocks:
        for block in blocks:
            results.append({
                'id' : block[0],
                'user_id' : block[1],
                'user_screen_name' : block[2],
                'victim_id' : block[3],
                'victim_screen_name' : block[4],
                'tweet_id' : block[5],
                'tweet_text' : block[6],
                'tweet_date' : block[7],
                'completed' : block[8],
                'created_at' : block[9],
            })

    return results


def update_block(id):
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    table_name = 'blocks'
    # B) Tries to insert an ID (if it does not exist yet)
    # with a specific value in a second column
    connection.execute("UPDATE "+table_name+" SET times=times+1, completed=:completed WHERE id=:id",
                       {
        'id':id,
        'completed':1
    })

    conn.commit()
    conn.close()

    return True


def block_for_me(oauth, user, victim, tweet, completed=False):
    try:
        import twitter
        api = twitter.Api(consumer_key=os.getenv('APP_CONSUMER_KEY'),
                          consumer_secret=os.getenv('APP_CONSUMER_SECRET'),
                          access_token_key=oauth['real_oauth_token'],
                          access_token_secret=oauth['real_oauth_token_secret'])
        api.CreateBlock(user_id=victim['id'], screen_name=victim['screen_name'])
    except Exception as e:
        print('Block Error: ', e)
        return False

    block = fetch_block(user['id'], victim['id'])
    # If block was pending, update. Else, create block
    if block:
        update_block(block['id'])
    else:
        save_block(user, victim, tweet, completed)
    return True


def print_error(_error):
    print(
        f"---------Error---------\n"
        f"Known error. Ignore. Nothing you can do.\n"
        f"{_error}\n"
        f"Sleeping for 1 minute then continuing.\n"
        f"-----------------------"
    )
    sleep(600)


def create_tables():
    conn = sqlite3.connect(sqlite_file)
    connection = conn.cursor()
    # Creating a new SQLite table with 1 column
    connection.execute('''
    CREATE TABLE if not exists oauths (
  id INTEGER PRIMARY KEY,
  screen_name varchar(191) NOT NULL,
  id_str varchar(191) NOT NULL,
  real_oauth_token varchar(191) NOT NULL,
  real_oauth_token_secret varchar(191) NOT NULL,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
    ''')

    connection.execute('''
     CREATE TABLE if not exists blocks (
  id INTEGER NOT NULL PRIMARY KEY,
  user_id varchar(191) NOT NULL,
  user_screen_name varchar(191) NOT NULL,
    victim_id varchar(191) NOT NULL,
  victim_screen_name varchar(191) NOT NULL,
  tweet_id varchar(191) NOT NULL,
  tweet_text varchar(191) NOT NULL,
  tweet_date timestamp NULL,
  completed TINYINT(1) DEFAULT 0,
   times INT(11) DEFAULT 0,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);
    ''')

    connection.execute('''
         CREATE TABLE if not exists tokens (
      id INTEGER NOT NULL PRIMARY KEY,
      token varchar(191) NOT NULL,
      secret varchar(191) NOT NULL,
      created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
        ''')

    # Committing changes and closing the connection to the database file
    conn.commit()
    conn.close()


def entry():
    create_tables()
    listener = StdOutListener()
    stream = Stream(auth, listener)

    print('Streaming started...')
    while True:
        try:
            stream.filter(track=[mention], is_async=True)
        except urllib3.exceptions.ProtocolError as error:
            print_error(_error=error)
        except ConnectionResetError as error:
            print_error(_error=error)
        except ConnectionError as error:
            print_error(_error=error)
        except requests.exceptions.ConnectionError as error:
            print_error(_error=error)
        except Exception as error:
            print(
                error,
                f"Sleeping for 5 minute then continuing."
            )
            sleep(3000)
