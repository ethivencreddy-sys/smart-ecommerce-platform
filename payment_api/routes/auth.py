import os
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from jose import jwt, JWTError

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse

from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password

from users.models import UserProfile

from payment_api.database import django
from payment_api.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
)
from payment_api.auth import create_access_token
from payment_api.dependencies import get_current_user

load_dotenv()

router = APIRouter()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")

AUTH0_ISSUER = (
    os.getenv("AUTH0_ISSUER")
    or f"https://{AUTH0_DOMAIN}/"
)

AUTH0_CALLBACK_URL = (
    "http://127.0.0.1:8001/api/auth/auth0/callback"
)


# ============================================================
# NORMAL REGISTER
# ============================================================

@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest):

    if User.objects.filter(
        username=data.username
    ).exists():

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    if User.objects.filter(
        email=data.email
    ).exists():

        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    user = User.objects.create_user(
        username=data.username,
        email=data.email,
        password=data.password
    )

    UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "role": "customer"
        }
    )

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ============================================================
# NORMAL LOGIN
# ============================================================

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):

    try:

        user = User.objects.get(
            email=data.email
        )

    except User.DoesNotExist:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not check_password(
        data.password,
        user.password
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "role": "customer"
        }
    )

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
def get_me(
    current_user=Depends(get_current_user)
):

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    }


# ============================================================
# AUTH0 LOGIN
# ============================================================

@router.get("/auth0/login")
def auth0_login():

    if not AUTH0_DOMAIN or not AUTH0_CLIENT_ID:

        raise HTTPException(
            status_code=500,
            detail="Auth0 configuration is missing"
        )

    # PKCE code verifier
    code_verifier = secrets.token_urlsafe(64)

    challenge_bytes = hashlib.sha256(
        code_verifier.encode("ascii")
    ).digest()

    code_challenge = (
        base64.urlsafe_b64encode(
            challenge_bytes
        )
        .decode("ascii")
        .rstrip("=")
    )

    # OAuth state
    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_CALLBACK_URL,

        # Keep the custom API audience.
        "audience": AUTH0_AUDIENCE,

        "scope": "openid profile email",

        "state": state,

        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorization_url = (
        f"https://{AUTH0_DOMAIN}/authorize?"
        f"{urlencode(params)}"
    )

    response = RedirectResponse(
        url=authorization_url,
        status_code=307
    )

    response.set_cookie(
        key="auth0_code_verifier",
        value=code_verifier,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=600
    )

    response.set_cookie(
        key="auth0_state",
        value=state,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=600
    )

    return response


# ============================================================
# AUTH0 CALLBACK
# ============================================================

@router.get("/auth0/callback")
def auth0_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None
):

    # --------------------------------------------------------
    # Validate authorization code
    # --------------------------------------------------------

    if not code:

        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing"
        )

    # --------------------------------------------------------
    # Validate OAuth state
    # --------------------------------------------------------

    stored_state = request.cookies.get(
        "auth0_state"
    )

    code_verifier = request.cookies.get(
        "auth0_code_verifier"
    )

    if not stored_state or not code_verifier:

        raise HTTPException(
            status_code=400,
            detail="PKCE session information is missing"
        )

    if not state or not secrets.compare_digest(
        state,
        stored_state
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    # --------------------------------------------------------
    # Exchange authorization code for Auth0 access token
    # --------------------------------------------------------

    token_url = (
        f"https://{AUTH0_DOMAIN}/oauth/token"
    )

    token_data = {
        "grant_type": "authorization_code",

        "client_id": AUTH0_CLIENT_ID,

        "client_secret": AUTH0_CLIENT_SECRET,

        "code": code,

        "redirect_uri": AUTH0_CALLBACK_URL,

        "code_verifier": code_verifier,

    }

    try:

        with httpx.Client(
            timeout=15
        ) as client:

            token_response = client.post(
                token_url,
                data=token_data
            )

    except Exception:

        raise HTTPException(
            status_code=502,
            detail="Unable to communicate with Auth0"
        )

    if token_response.status_code != 200:

        raise HTTPException(
            status_code=401,
            detail="Auth0 token exchange failed"
        )

    tokens = token_response.json()

    access_token = tokens.get(
        "access_token"
    )

    if not access_token:

        raise HTTPException(
            status_code=401,
            detail="Auth0 access token was not returned"
        )

    # --------------------------------------------------------
    # Retrieve Auth0 signing keys
    # --------------------------------------------------------

    jwks_url = (
        f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    )

    try:

        with httpx.Client(
            timeout=15
        ) as client:

            jwks_response = client.get(
                jwks_url
            )

    except Exception:

        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Auth0 signing keys"
        )

    if jwks_response.status_code != 200:

        raise HTTPException(
            status_code=401,
            detail="Unable to retrieve Auth0 signing keys"
        )

    jwks = jwks_response.json()

    # --------------------------------------------------------
    # Read JWT header
    # --------------------------------------------------------

    try:

        unverified_header = jwt.get_unverified_header(
            access_token
        )

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid Auth0 access token"
        )

    # --------------------------------------------------------
    # Find matching RSA key
    # --------------------------------------------------------

    rsa_key = None

    for key in jwks.get("keys", []):

        if key.get("kid") == unverified_header.get(
            "kid"
        ):

            rsa_key = key
            break

    if rsa_key is None:

        raise HTTPException(
            status_code=401,
            detail="Unable to find Auth0 signing key"
        )

    # --------------------------------------------------------
    # Validate Auth0 access token
    # --------------------------------------------------------

    try:

        claims = jwt.decode(
            access_token,
            rsa_key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=AUTH0_ISSUER,
        )

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid Auth0 access token"
        )

    # --------------------------------------------------------
    # Auth0 user identity
    # --------------------------------------------------------

    auth0_sub = claims.get(
        "sub"
    )

    if not auth0_sub:

        raise HTTPException(
            status_code=400,
            detail="Auth0 token does not contain a user identity"
        )

    # --------------------------------------------------------
    # Try standard profile claims
    #
    # Auth0 third-party API access tokens normally contain
    # the subject but may not contain email/name claims.
    # --------------------------------------------------------

    email = claims.get("email")

    name = (
        claims.get("name")
        or claims.get("nickname")
        or claims.get("preferred_username")
    )

    # --------------------------------------------------------
    # Find existing Auth0-linked local user
    # --------------------------------------------------------

    username_base = (
        name
        or f"auth0_{auth0_sub.replace('|', '_')}"
    )

    username_base = username_base.replace(
        " ",
        "_"
    )

    user = None

    # If email is available, use it first.
    if email:

        user = User.objects.filter(
            email=email
        ).first()

    # If no user exists, create one.
    if not user:

        username = username_base

        counter = 1

        while User.objects.filter(
            username=username
        ).exists():

            username = (
                f"{username_base}{counter}"
            )

            counter += 1

        # Auth0 third-party API tokens may not contain email.
        # Create a safe local placeholder email when necessary.
        local_email = (
            email
            or f"{auth0_sub.replace('|', '_')}@auth0.local"
        )

        user = User.objects.create_user(
            username=username,
            email=local_email
        )

    # --------------------------------------------------------
    # Create customer profile
    # --------------------------------------------------------

    UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "role": "customer"
        }
    )

    # --------------------------------------------------------
    # Create our application's local JWT
    # --------------------------------------------------------

    local_token = create_access_token({
        "sub": str(user.id),
        "email": user.email
    })

    # --------------------------------------------------------
    # Return local authentication response
    # --------------------------------------------------------

    response = JSONResponse({
        "message": "Auth0 login successful",

        "access_token": local_token,

        "token_type": "bearer",

        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    })

    # --------------------------------------------------------
    # Remove OAuth temporary cookies
    # --------------------------------------------------------

    response.delete_cookie(
        "auth0_code_verifier"
    )

    response.delete_cookie(
        "auth0_state"
    )

    return response