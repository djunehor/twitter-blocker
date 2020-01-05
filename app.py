import os
from flask import Flask, render_template, request
import oauth2 as oauth
import urllib.request
import urllib.parse
import urllib.error
import json
from tweet_stream import block_for_me, save_oauth, fetch_oauth, update_oauth, entry, fetch_pending_block, fetch_blocks, \
    save_token, fetch_token, delete_token, fetch_oauth_by_username

# Experimental
# try:
#     os.system("pkill -f tweet_stream.py")
# except:
#     pass

# We're creating separate thread for streaming
# so it starts whenever server starts and it keeps running

app = Flask(__name__)
app.secret_key = os.urandom(24)

request_token_url = 'https://api.twitter.com/oauth/request_token'
access_token_url = 'https://api.twitter.com/oauth/access_token'
authorize_url = 'https://api.twitter.com/oauth/authorize'
show_user_url = 'https://api.twitter.com/1.1/users/show.json'

# Support keys from environment vars (Heroku).
app.config['APP_CONSUMER_KEY'] = os.getenv(
    'APP_CONSUMER_KEY', 'API_Key_from_Twitter')
app.config['APP_CONSUMER_SECRET'] = os.getenv(
    'APP_CONSUMER_SECRET', 'API_Secret_from_Twitter')

app_callback_url = os.getenv('APP_URL') + '/callback'


@app.route('/')
def home():
    return render_template(
        'index.html',
        title="Home",
        app_name=os.getenv('APP_NAME')
    )


@app.route('/user/<username>')
def user(username):
    user_oauth = fetch_oauth_by_username(username)
    # print(username, user_oauth)
    if not user_oauth:
        error_message = "It seems you haven't authorized " + os.getenv('APP_NAME') + " on your twitter account."
        return render_template(
            'error.html',
            app_name=os.getenv('APP_NAME'),
            error_message=error_message,
            title="Not Found"
        )

    blocks = fetch_blocks(username)
    return render_template(
        'user.html',
        blocks=blocks,
        username=username,
        title=username,
        app_name=os.getenv('APP_NAME')
    )


@app.route('/start')
def start():
    global app_callback_url
    # note that the external callback URL must be added to the whitelist on
    # the developer.twitter.com portal, inside the app settings

    # Generate the OAuth request tokens, then display them
    consumer = oauth.Consumer(
        app.config['APP_CONSUMER_KEY'], app.config['APP_CONSUMER_SECRET'])
    client = oauth.Client(consumer)
    # print('Call back: ', app_callback_url)
    resp, content = client.request(request_token_url, "POST", body=urllib.parse.urlencode({
        "oauth_callback": app_callback_url}))

    if resp['status'] != '200':
        error_message = 'Invalid response, status {status}, {message}'.format(
            status=resp['status'], message=content.decode('utf-8'))
        return render_template(
            'error.html',
            app_name=os.getenv('APP_NAME'),
            error_message=error_message,
            title="API Error"
        )

    request_token = dict(urllib.parse.parse_qsl(content))
    oauth_token = request_token[b'oauth_token'].decode('utf-8')
    oauth_token_secret = request_token[b'oauth_token_secret'].decode('utf-8')

    save_token(oauth_token_secret, oauth_token)
    return render_template(
        'start.html',
        app_name=os.getenv('APP_NAME'),
        authorize_url=authorize_url,
        oauth_token=oauth_token,
        request_token_url=request_token_url,
        title='Start'
    )


@app.route('/callback')
def callback():
    global app_callback_url
    # Accept the callback params, get the token and call the API to
    # display the logged-in user's name and handle
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    oauth_denied = request.args.get('denied')
    oauth_store = fetch_token(oauth_token)

    # print(oauth_store)

    # if the OAuth request was denied, delete our local token
    # and show an error message
    if oauth_denied:
        if oauth_denied in oauth_store:
            del oauth_store[oauth_denied]
        return render_template(
            'error.html',
            error_message="the OAuth request was denied by this user",
            app_name=os.getenv('APP_NAME'),
            title="Authentication Error"
        )

    if not oauth_token or not oauth_verifier:
        return render_template(
            'error.html',
            error_message="callback param(s) missing",
            app_name=os.getenv('APP_NAME'),
            title="Authentication Error"

        )

    # unless oauth_token is still stored locally, return error
    if oauth_token not in oauth_store:
        return render_template(
            'error.html',
            error_message="oauth_token not found locally",
            app_name=os.getenv('APP_NAME'),
            title="Authentication Error"
        )

    # print(oauth_store)

    oauth_token_secret = oauth_store[oauth_token]

    # if we got this far, we have both callback params and we have
    # found this token locally

    consumer = oauth.Consumer(
        app.config['APP_CONSUMER_KEY'], app.config['APP_CONSUMER_SECRET'])
    token = oauth.Token(oauth_token, oauth_token_secret)
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)

    resp, content = client.request(access_token_url, "POST")
    access_token = dict(urllib.parse.parse_qsl(content))

    screen_name = access_token[b'screen_name'].decode('utf-8')
    user_id = access_token[b'user_id'].decode('utf-8')

    user = {'screen_name': screen_name, 'id': user_id}

    # These are the tokens you would store long term, someplace safe
    real_oauth_token = access_token[b'oauth_token'].decode('utf-8')
    real_oauth_token_secret = access_token[b'oauth_token_secret'].decode(
        'utf-8')

    oauth_store['real_oauth_token'] = real_oauth_token
    oauth_store['real_oauth_token_secret'] = real_oauth_token_secret

    # Call api.twitter.com/1.1/users/show.json?user_id={user_id}
    real_token = oauth.Token(real_oauth_token, real_oauth_token_secret)
    real_client = oauth.Client(consumer, real_token)
    real_resp, real_content = real_client.request(
        show_user_url + '?user_id=' + user_id, "GET")

    if real_resp['status'] != '200':
        error_message = "Invalid response from Twitter API GET users/show: {status}".format(
            status=real_resp['status'])
        return render_template(
            'error.html',
            error_message=error_message,
            app_name=os.getenv('APP_NAME'),
            title="Authentication Error"
        )

    response = json.loads(real_content.decode('utf-8'))

    friends_count = response['friends_count']
    statuses_count = response['statuses_count']
    followers_count = response['followers_count']
    name = response['name']

    # don't keep this token and secret in temp any longer
    delete_token(oauth_token)

    pending_action = fetch_pending_block(user_id)

    success_message = ''
    error_message = ''

    if pending_action:
        victim = {
            'id': pending_action['victim_id'],
            'screen_name': pending_action['victim_screen_name'],
        }
        tweet = {
            'id': pending_action['tweet_id'],
            'text': pending_action['tweet_text'],
            'created_at': pending_action['tweet_date'],
        }

        try:
            block_for_me(oauth_store, user, victim, tweet, True)

            success_message = "User @" + pending_action['victim_screen_name'] + " has been blocked for you."
        except Exception as e:
            print('Block Error: ', e)
            error_message = "An error occurred while trying to block User @" + pending_action[
                'victim_screen_name'] + " for you."

    new_oauth = fetch_oauth(user['id'])
    if new_oauth:
        update_oauth(oauth_store, new_oauth['id'])
    else:
        save_oauth(oauth_store, user)

    return render_template(
        'callback-success.html',
        app_name=os.getenv('APP_NAME'),
        screen_name=screen_name,
        user_id=user_id, name=name,
        user_url=os.getenv('APP_URL') + '/user/' + screen_name,
        friends_count=friends_count,
        statuses_count=statuses_count,
        followers_count=followers_count,
        access_token_url=access_token_url,
        error_message=error_message,
        success_message=success_message,
        title='Success'
    )


@app.errorhandler(500)
def internal_server_error(e):
    print('App Error: ', e)
    return render_template(
        'error.html',
        error_message='Uncaught exception',
        app_name=os.getenv('APP_NAME'),
        title='Internal Server Error'
    ), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, use_reloader=False)
