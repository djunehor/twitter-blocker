# Twitter Blocker App

A simple Twitter bot to help block users more efficiently
- https://twitter-please-block.herokuapp.com

## Setup
Ensure you have Python 3 installed on your device.
1. Git clone this repo
2. Obtain consumer key and secret from the Twitter Developer portal. The app should be configured to enable Sign in with Twitter:
3. `cd twitter-app`.
4. On your local setup, create an `.env` and Set env variables:
```
APP_NAME
APP_URL
APP_CONSUMER_KEY
APP_CONSUMER_SECRET
APP_ACCESS_TOKEN
APP_ACCESS_TOKEN_SECRET
```
5. Setup a [pipenv](https://pipenv.readthedocs.io/en/latest/) environment, and install dependencies:
   1. `virtualenv twitter-app`
   2. `source ../twitter-app/bin/activate` on mac or `../twitter-app/bin/activate` windows
   3. `pip install -r requirements.txt`
6. Start the app:
   1. `python app.py`; or
   2. `gunicorn app:app`

> Note: A `Procfile` is included for deployment to cloud solutions.

Finally, revisit the dev portal, and add your app's callback URL (https://your-deployed-url/callback e.g `http://127.0.0.1:8000/callback`) to the callback URL whitelist setting. Once saved, follow the instructions on the app's web UI to click through the demo pages.

## Reference

[Twitter Developer Portal](https://developer.twitter.com/)  
[Flask](https://flask.pocoo.org/)  
[python-oauth2](https://github.com/simplegeo/python-oauth2)  
[Bootstrap](https://getbootstrap.com/)  

### Credits

Original version by Zacchaeus Bolaji
- https://twitter.com/djunehor
- https://github.com/djunehor

## Contributing
- Fork the project
- Pull to your local device
- Make your changes and push
- Create a Pull Request using this [template](https://github.com/djunehor/twitter-blocker/blob/master/.github/PULL_REQUEST_TEMPLATE.md)
