from app import app
from app.util import c_requests
from flask import session
import os
import json

def oidc_proxy_userinfo(token):
    data = {
    'client_id': app.config.get('AUTHENTICATION_CLIENT_ID'),
    'client_secret':app.config.get('AUTHENTICATION_CLIENT_SECRET'),
    }
    headers= {
        "Authorization":f"Bearer {token}",
        "Content-Type" : "application/x-www-form-urlencoded"
    }

    uri_userinfo = f"{app.config.get('OIDC_ISSUER_URL')}/protocol/openid-connect/userinfo"

    response = c_requests(uri_userinfo, headers, data)

    return response

def oidc_proxy_authenticate(code):
    success = False
    data = {
    'client_id': app.config.get('AUTHENTICATION_CLIENT_ID'),
    'client_secret':app.config.get('AUTHENTICATION_CLIENT_SECRET'),
    'grant_type':'authorization_code',
    'code':code,
    'redirect_uri':f"https://{app.config.get('IRIS_UPSTREAM_SERVER')}/auth"
    }
    headers={}

    uri_token=f"{app.config.get('OIDC_ISSUER_URL')}/protocol/openid-connect/token"
    
    response = c_requests(uri_token, headers, data)

    if "access_token" in response:
        session["oidc_access_token"] = response["access_token"]
        session["oidc_refresh_token"] = response["refresh_token"]
        session.modified = True
        success=True

    return success

def oidc_proxy_logout():
    if "oidc_refresh_token" in session.keys():
        data = {
        'client_id': app.config.get('AUTHENTICATION_CLIENT_ID'),
        'client_secret':app.config.get('AUTHENTICATION_CLIENT_SECRET'),
        "refresh_token" : f'{session["oidc_refresh_token"]}'
        }
        headers= {
            "Authorization":f"Bearer {session['oidc_access_token']}",
            "Content-Type" : "application/x-www-form-urlencoded"
        }

        #response = requests.post(f"{app.config.get('OIDC_ISSUER_URL')}/protocol/openid-connect/logout", data=data, headers=headers)

        uri_logout = f"{app.config.get('OIDC_ISSUER_URL')}/protocol/openid-connect/logout"

        response = c_requests(uri_logout, headers, data)

    return