import os
from apiflask import HTTPBasicAuth


GUEST_USER = os.environ.get("GUEST_USER", "sso")
GUEST_PASS = os.environ.get("GUEST_PASS", "changeme")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")


guest_auth = HTTPBasicAuth(description="Guest Authentication")
admin_auth = HTTPBasicAuth(description="Admin Authentication")


@guest_auth.verify_password
def verify_guest_auth(username, password):
    if username == GUEST_USER and password == GUEST_PASS: return True
    else: return False


@admin_auth.verify_password
def verify_admin_auth(username, password):
    if username == ADMIN_USER and password == ADMIN_PASS: return True
    else: return False
