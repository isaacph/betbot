#!/usr/bin/python
# this script sets the commands for a Discord application
# run this with Python 3.11

import requests
from public_key import AUTH_TOKEN, APPLICATION_ID
# AUTH_TOKEN is bot secret key, formatted like 'Bot <base64 stuff>.<stuff>.<stuff>_<stuff>-<stuff>'
# APPLICATION_ID is bot application ID

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

to_delete = []

# This is an example CHAT_INPUT or Slash Command, with a type of 1
json = {
    "name": "bb",
    "type": 1,
    "description": "Place bets, decide the winner",
    "options": [
        {
            "name": "bank",
            "description": "Check your bank, and receive money once daily",
            "type": 1,
            "required": False,
        },
        {
            "name": "bet",
            "description": "Place a bet against another user",
            "type": 1,
            "required": False,
            "options": [
                {
                    "name": "against",
                    "description": "The user you are betting against",
                    "type": 6,
                    "required": True,
                },
                {
                    "name": "arbitrator",
                    "description": "The user who decides the winner",
                    "type": 6,
                    "required": True,
                },
                {
                    "name": "amount",
                    "description": "The amount you are betting",
                    "type": 4,
                    "required": True,
                },
                {
                    "name": "condition",
                    "description": "Better wins if:",
                    "type": 3,
                    "required": True,
                },
            ]
        },
        {
            "name": "accept",
            "description": "Accept a bet against a user",
            "type": 1,
            "required": False,
            "options": [
                {
                    "name": "against",
                    "description": "The user who placed a bet on you",
                    "type": 6,
                    "required": True,
                },
            ]
        },
        {
            "name": "reject",
            "description": "Reject a bet against a user",
            "type": 1,
            "required": False,
            "options": [
                {
                    "name": "against",
                    "description": "The user who placed a bet on you",
                    "type": 6,
                    "required": True,
                },
            ]
        },
        {
            "name": "decide",
            "description": "Decide a bet between users, if you are the arbitrator",
            "type": 1,
            "required": False,
            "options": [
                {
                    "name": "victor",
                    "description": "The user who should win the bet",
                    "type": 6,
                    "required": True,
                },
                {
                    "name": "loser",
                    "description": "The user who should lose the bet",
                    "type": 6,
                    "required": True,
                },
            ]
        },
        {
            "name": "cancel",
            "description": "Cancel a bet with another user. Requires consent from other user",
            "type": 1,
            "required": False,
            "options": [
                {
                    "name": "against",
                    "description": "The user you want to cancel your bet with",
                    "type": 6,
                    "required": True,
                }
            ]
        }
    ]
}

# For authorization, you can use either your bot token
headers = {
    "Authorization": AUTH_TOKEN
}

r = requests.post(url, headers=headers, json=json)

print(r.status_code)
print(r.text)

if len(to_delete) > 0:
    print(f"Trying {len(to_delete)} delete requests")
    print("Querying commands")
    r = requests.get(url, headers=headers)
    print(r.status_code)
    print(r.text)
    print(r.json())
    for x in r.json():
        delete_name = x['name']
        if delete_name in to_delete:
            delete_id = x['id']
            print(f"Will delete {delete_name}: id is {delete_id}")
            delete_url = url + "/" + delete_id
            r = requests.delete(delete_url, headers=headers)
            print(f"Delete {delete_name} -- {r.status_code}\n{r.text}\n")

