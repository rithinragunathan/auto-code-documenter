import requests
from main import WEBHOOK_URL
response = requests.post(
            WEBHOOK_URL,
            json={"documentation": "Example documentation text"},
            auth=("user", "afc4e2c6-4e07-4ff3-97d8-13fcc2a873a8"),
        )