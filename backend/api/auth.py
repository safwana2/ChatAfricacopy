# This script handles Google OAuth authentication using Flask Blueprint 
import os
import pathlib
from dotenv import load_dotenv

# flask libraries
import requests
from flask import Flask, session, abort, redirect, request, Blueprint, render_template
from flask_login import current_user, login_user, logout_user

# Google OAuth libraries
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

# Import models
from .. import db
from ..models.user import User


load_dotenv()

# Load environment variables
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# define blueprint
auth = Blueprint('auth', __name__)

# Initializing the application with Google Credentials
app = Flask(__name__)
app.secret_key = GOOGLE_CLIENT_SECRET

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # to allow Http traffic for local dev


# Define Google client ID, secrets file, and flow object for authentication
GOOGLE_CLIENT_ID = GOOGLE_CLIENT_ID
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/login/callback"
)


# """Custom Authentication decorator function"""
# def login_is_required(function):
#     def wrapper(*args, **kwargs):
#         if "google_id" not in session:
#             return abort(401)  # Authorization required
#         else:
#             return function(*args, **kwargs)

#     return wrapper
@auth.route("/sign-in")
def signin():
    return render_template("sign_in.html", user=current_user)

# Initiate Google Auth
@auth.route("/login")
def login():
    """ Check user login """
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

# Google OAuth2 callback function to login user
@auth.route("/login/callback")
def callback():
    """ Initiate Google OAuth2 flow """
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    # Check if user with same google id already exists
    user = User.query.filter_by(google_id=id_info.get("sub")).first()
    
    # Log in user if user exists
    if user:
        login_user(user)
        return (redirect('/chats'))

    # Create a new User if google_id is not in database
    new_user = User(
        google_id=id_info.get("sub"),
        name=id_info.get("name"),
        email=id_info.get("email"),
        avatar_url=id_info.get("picture")
    )
    db.session.add(new_user)
    db.session.commit()

    # Log in new user
    login_user(new_user)
    return redirect('/chats')


# Route to log out user
@auth.route("/logout")
def logout():
    logout_user()
    return redirect('/')


@auth.route("/")
def index():
    if "google_id" in session:
        return redirect('/chats')
    else:
        # return "Hello World!<a href='/login'><button>Login</button></a>"
        return render_template('landing.html', user=current_user)


# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True, load_dotenv=True)
