from tweepy import API, OAuthHandler, Stream, StreamListener
from time import sleep
from dotenv import load_dotenv
from threading import Thread
import os
import mysql.connector
import random

load_dotenv('.env')

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

auth_url = str(os.getenv('APP_URL')) + '/start'

mydb = None

messages = [
    'Hello',
    'Hi'
    'Bonjour',
    'Hoi',
    'Salam',
    'Hallo',
    'Namastē',
    'Olá',
    'Hallå',
    'Sawubona'
]


class StdOutListener(StreamListener):
    """ A listener handles tweets that are received from the stream.
    This is a basic listener that just prints received tweets to stdout.
    """

    def on_status(self, status):
        # Using threads so incoming requests can be attended to simultenously
        Thread(target=handle(status)).start()

    def on_error(self, status):
        print('Error occurred: ', status)
        return True


def handle(data):

    # let's grab some data we need
    tweet_id = data.id_str  # we need this so bot can quote tweet when replying
    user_id = data.user.id_str

    # Not in use at the moment
    tweet = data.text
    handle = data.user.screen_name

    # avoid infinite loop
    if handle.lower() == mention.lower():
        return

    # if no tweet quoted or can't be found
    if not data.in_reply_to_status_id:
        return

    # if in reply to multiple users https://twitter.com/dara_tobi/status/1213220598018715648
    # if 'entities' in decoded and 'user_mentions' in decoded['entities'] and len(decoded['entities']['user_mentions']) > 1:
    #     return

    # if keyword not included https://twitter.com/theshalvah/status/1213218709403262979
    if 'block' not in str(tweet.replace(mention, '')).lower():
        return
    else:
        # `we need to fetch the quoted tweet so we can save sa evidence
        tweet_object = api.get_status(data.in_reply_to_status_id)

        if not tweet_object:
            return
        tweet = {
            'id': tweet_object.id,
            'id_str': tweet_object.id_str,
            'text': tweet_object.text,
            'created_at': tweet_object.created_at,
            'user': {
                'id': tweet_object.user.id,
                'id_str': tweet_object.user.id_str,
                'screen_name': tweet_object.user.screen_name,
            },
        }

        # If quoted user is the poster user
        if handle == tweet['user']['screen_name']:
            return

        user = {
            'id' : data.user.id,
            'id_str' : data.user.id_str,
            'screen_name' : data.user.screen_name,
        }
        # if no oauth
        oauth = fetch_oauth(user_id)
        if not oauth:
            # Todo: Refactor rotating texts
            # Tell user to authenticate us, so we can complete his/her request
            text1 = random.choice(messages)+" @"+user['screen_name']+", I noticed you've not given me permission to block on your behalf. Kindly " \
                    "visit " + auth_url + " to do that and I'll complete the action once that's done."
            text2 = random.choice(messages)+" @"+user['screen_name']+", I need one more thing. Please go here " + auth_url + " to grant me permission to block on your behalf."
            text3 = random.choice(messages)+" @"+user['screen_name']+", please visit " + auth_url + " and follow the instructions for me to complete your request."
            text4 = random.choice(messages)+" @"+user['screen_name']+", you need to authenticate here " + auth_url + " before I can block for you."
            text5 = random.choice(messages)+" @"+user['screen_name']+", once you authenticate here " + auth_url + " I won't ask for authentication again."

            # Experimenting with alternating texts
            text = random.choice([text1, text2, text3, text4, text5])

            # save block request if no pending, but mark as incomplete
            if not fetch_block(user['id'], tweet['user']['id'], False):
                save_block(user, tweet['user'], tweet, False)
        else:
            block = block_for_me(oauth, user, tweet['user'], tweet, True)

            if block:
                # Another random text
                random_texts = [
                    random.choice(messages)+" @"+user['screen_name']+", User has been blocked for you.",
                    random.choice(messages)+" @"+user['screen_name']+", Done!",
                    random.choice(messages)+" @"+user['screen_name']+", Transaction complete!",
                    random.choice(messages)+" @"+user['screen_name']+", You won't hear from @" + tweet['user']['screen_name'] + " again.",
                    random.choice(messages)+" @"+user['screen_name']+", User won't show on your timeline again.",
                    random.choice(messages)+" @"+user['screen_name']+", I have blocked the user for you.",
                    random.choice(messages)+" @"+user['screen_name']+", User is blocked",
                    random.choice(messages)+" @"+user['screen_name']+", User blocked",
                    random.choice(messages)+" @"+user['screen_name']+", User has been served a RED card",
                    random.choice(messages)+" @"+user['screen_name']+", "+tweet['user']['screen_name'] +" will no longer show on your timeline.",
                    random.choice(messages)+" @"+user['screen_name']+", I'm sure you have good reasons. I've blocked the user as requested.",
                    random.choice(messages)+" @"+user['screen_name']+", Sometimes, it's best to avoid some people than engage. User blocked.",
                    random.choice(messages)+" @"+user['screen_name']+", I'm sure this is the right decision. User has been blocked for you.",
                    random.choice(messages)+" @"+user['screen_name']+", View your blocked users here "+os.getenv('APP_URL')+"/start"
                ]
                text = random.choice(random_texts)
            else:
                # Blocking failed na, so?
                text = ''

    # Tweet reply
    # Found out tweet will only be a reply if user is tagged/mentioned in the reply
    api.update_status(text, in_reply_to_status_id = tweet_id)
    # save_reply(tweet_id, text)

# In order to avoid "MySQL has gone away error. I'm reconnecting to the DB for each DB transaction
# Todo: Find a more efficient way of persistent DB connection


def db_connect():
    global mydb
    mydb = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        passwd=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

    return mydb.cursor(buffered=True)


def fetch_reply(tweet_id):
    connection = db_connect()
    table_name = 'replies'

    connection.execute('SELECT * FROM `' + table_name + '` WHERE `tweet_id`=%s',
                       (tweet_id,))
    reply = connection.fetchone()

    return {
        'id': reply[0],
        'tweet_id': reply[1],
        'message': reply[2],
        'created_at': reply[3],
    } if reply else {}


def save_reply(tweet_id, text):
    connection = db_connect()
    table_name = 'replies'

    connection.execute("INSERT INTO " + table_name +
                       "(tweet_id, message) "
                       "VALUES ( %s, %s)",
                       (
                           tweet_id,
                           text
                       ))

    mydb.commit()

    return True


def fetch_oauth(user_id):
    connection = db_connect()
    table_name = 'oauths'

    connection.execute('SELECT * FROM `' + table_name + '` WHERE `id_str`=%s',
                       (user_id,))
    oauth = connection.fetchone()

    return {
        'id': oauth[0],
        'screen_name': oauth[1],
        'id_str': oauth[2],
        'real_oauth_token': oauth[3],
        'real_oauth_token_secret': oauth[4],
        'created_at': oauth[5],
    } if oauth else {}


def fetch_oauth_by_username(screen_name):
    connection = db_connect()
    table_name = 'oauths'

    connection.execute('SELECT * FROM `' + table_name + '` WHERE `screen_name`=%s',
                       (screen_name,))

    oauth = connection.fetchone()

    return {
        'id': oauth[0],
        'screen_name': oauth[1],
        'id_str': oauth[2],
        'real_oauth_token': oauth[3],
        'real_oauth_token_secret': oauth[4],
        'created_at': oauth[5],
    } if oauth else {}


def update_oauth(oauth, id):
    connection = db_connect()
    table_name = 'oauths'

    query = "UPDATE `" + table_name + "` SET real_oauth_token = %s, real_oauth_token_secret = %s WHERE id = %s"
    connection.execute(query, (oauth['real_oauth_token'], oauth['real_oauth_token_secret'], id))

    mydb.commit()

    return True


def save_oauth(oauth, user):
    connection = db_connect()
    table_name = 'oauths'

    connection.execute("INSERT INTO " + table_name +
                       "(screen_name, id_str, real_oauth_token, real_oauth_token_secret) "
                       "VALUES ( %s, %s, %s, %s )",
                       (

                           user['screen_name'],
                           user['id'],
                           oauth['real_oauth_token'],
                           oauth['real_oauth_token_secret'],
                       ))

    mydb.commit()

    return True


# Not in use
def validate_oauth(oauth):
    try:
        auth.set_access_token(oauth['real_access_token'], oauth['access_token_secret'])
        api = API(auth)
        api.get_user()
        return True
    except:
        return None


def save_block(user, victim, tweet, completed=True):
    connection = db_connect()
    if not isinstance(user, dict):
        user = dict(user)
    if not isinstance(victim, dict):
        victim = dict(victim)
    if not isinstance(tweet, dict):
        tweet = dict(tweet)

    table_name = 'blocks'

    connection.execute("INSERT INTO  " + table_name +
                       "( user_id, user_screen_name, victim_id, victim_screen_name, tweet_id, tweet_text, tweet_date, completed ) "
                       "VALUES ( "
                       "%s, %s, %s, %s, %s, %s, %s, %s"
                       " )"
                       , (
                           user['id'],
                           user['screen_name'],
                           victim['id'],
                           victim['screen_name'],
                           tweet['id'],
                           tweet['text'],
                           tweet['created_at'],
                           1 if completed else 0
                       ))

    mydb.commit()

    return True


def save_token(secret, token):
    connection = db_connect()
    table_name = 'tokens'

    connection.execute("INSERT INTO  " + table_name +
                       "( token, secret ) "
                       "VALUES ( "
                       "%s, %s"
                       " )"
                       , (
                           token,
                           secret,
                       ))
    mydb.commit()

    return True


def fetch_token(token):
    connection = db_connect()
    table_name = 'tokens'

    connection.execute("SELECT * FROM  " + table_name + " WHERE token=%s"
                       , (
                           token,
                       ))

    token = connection.fetchone()

    return {
        token[1]: token[2],
    } if token else None


def delete_token(token):
    connection = db_connect()
    table_name = 'tokens'
    connection.execute('DELETE FROM `' + table_name + '` WHERE `token`=%s', (token,))
    mydb.commit()

    return True


def fetch_block(user_id, victim_id, completed=None):
    connection = db_connect()
    table_name = 'blocks'

    if completed:
        connection.execute(
            'SELECT * FROM ' + table_name + ' WHERE user_id=%s AND victim_id=%s AND completed=%s ORDER BY id DESC LIMIT 1',
            (user_id, victim_id, int(completed)))
    else:
        connection.execute(
            'SELECT * FROM ' + table_name + ' WHERE user_id=%s AND victim_id=%s ORDER BY id DESC LIMIT 1',
            (user_id, victim_id))
    block = connection.fetchone()

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
    connection = db_connect()
    table_name = 'blocks'

    connection.execute(
        'SELECT * FROM `' + table_name + '` WHERE `user_id`=%s AND `completed`=0 ORDER BY id DESC LIMIT 1',
        (user_id,))
    block = connection.fetchone()

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


def fetch_blocks(username):
    connection = db_connect()
    table_name = 'blocks'

    connection.execute(
        'SELECT * FROM `' + table_name + '` WHERE `user_screen_name`=%s ORDER BY id',
        (username,))
    blocks = connection.fetchall()

    results = []
    if blocks:
        for block in blocks:
            results.append({
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
            })

    return results


def update_block(id):
    connection = db_connect()
    table_name = 'blocks'
    # B) Tries to insert an ID (if it does not exist yet)
    # with a specific value in a second column
    connection.execute("UPDATE `" + table_name + "` SET `times`=times+1, `completed`=%s WHERE `id`=%s",
                       (
                           id,
                           1
                       ))

    mydb.commit()

    return True


def block_for_me(oauth, user, victim, tweet, completed=False):
    try:
        new_auth = OAuthHandler(consumer_key, consumer_secret)
        new_auth.set_access_token(oauth['real_oauth_token'], oauth['real_oauth_token_secret'])
        new_api = API(new_auth)
        new_api.create_block(user_id=victim['id'], screen_name=victim['screen_name'])
        del new_auth, new_api
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
    connection = db_connect()
    # Creating a new SQLite table with 1 column
    connection.execute('''
    CREATE TABLE if not exists oauths (
  id INT AUTO_INCREMENT PRIMARY KEY,
  screen_name varchar(191) NOT NULL,
  id_str varchar(191) NOT NULL,
  real_oauth_token varchar(191) NOT NULL,
  real_oauth_token_secret varchar(191) NOT NULL,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW() ON UPDATE NOW()
);
    ''')

    connection.execute('''
     CREATE TABLE if not exists blocks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id varchar(191) NOT NULL,
  user_screen_name varchar(191) NOT NULL,
    victim_id varchar(191) NOT NULL,
  victim_screen_name varchar(191) NOT NULL,
  tweet_id varchar(191) NOT NULL,
  tweet_text varchar(191) NOT NULL,
  tweet_date timestamp NULL,
  completed TINYINT(1) DEFAULT 0,
   times INT(11) DEFAULT 0,
  created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW() ON UPDATE NOW()
);
    ''')

    connection.execute('''
         CREATE TABLE if not exists tokens (
      id INT AUTO_INCREMENT PRIMARY KEY,
      token varchar(191) NOT NULL,
      secret varchar(191) NOT NULL,
      created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP NOT NULL DEFAULT NOW() ON UPDATE NOW()
    );
        ''')

    connection.execute('''
             CREATE TABLE if not exists replies (
          id INT AUTO_INCREMENT PRIMARY KEY,
          tweet_id varchar(191) NOT NULL,
          message varchar(191) NOT NULL,
          created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP NOT NULL DEFAULT NOW() ON UPDATE NOW()
        );
            ''')

    # Committing changes and closing the connection to the database file
    mydb.commit()


def entry():
    create_tables()

    import subprocess

    cmd = ['pgrep -f .*python.*tweet_stream.py']
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    my_pid, err = process.communicate()

    if len(my_pid.splitlines()) > 0:
        print("Running: ", my_pid)
        os.system('pkill -f '+__file__)
    else:
        print("Not Running")

    listener = StdOutListener()
    stream = Stream(auth, listener)

    print('Streaming started...')
    stream.filter(track=[mention], is_async=True)


if __name__ == '__main__':
    entry()
