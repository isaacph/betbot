from __future__ import annotations
import datetime
from typing import cast
from contextlib import contextmanager
from io import SEEK_SET
from typing import Dict
from public_key import PUBLIC_KEY, BANK_DIR
from dataclasses import dataclass
from dataclass_wizard import JSONWizard
import humanize

from nacl.signing import VerifyKey
import os

PING_PONG = {"type": 1}
RESPONSE_TYPES =  { 
                    "PONG": 1, 
                    #"ACK_NO_SOURCE": 2, 
                    #"MESSAGE_NO_SOURCE": 3, 
                    "MESSAGE_WITH_SOURCE": 4, 
                    "ACK_WITH_SOURCE": 5
                  }
PAYCHECK = 1000
PAYCHECK_FREQUENCY = datetime.timedelta(days=1)
#PUBLIC_KEY = '' # found on Discord Application -> General Information page

def verify_signature(event):
    raw_body = event.get("rawBody")
    auth_sig = event['params']['header'].get('x-signature-ed25519')
    auth_ts  = event['params']['header'].get('x-signature-timestamp')
    
    message = auth_ts.encode() + raw_body.encode()
    verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
    verify_key.verify(message, bytes.fromhex(auth_sig)) # raises an error if unequal

def ping_pong(body):
    if body.get("type") == 1:
        return True
    return False


def lambda_handler(event, _):
    print(f"event {event}") # debug print
    # verify the signature
    try:
        verify_signature(event)
    except Exception as e:
        raise Exception(f"[UNAUTHORIZED] Invalid request signature: {e}")

    resp = {
        "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
        "data": {
            "tts": False,
            "content": "Somehow there's no response!",
            "embeds": [],
            "allowed_mentions": []
        }
    };

    # check if message is a ping
    body = event.get('body-json')
    if ping_pong(body):
        resp = PING_PONG
    else:
        command = "No command"
        options = "No options"
        try:
            # open server
            server_id = body.get('guild_id')
            with server(server_id) as bank:
                # get user
                user_id = body.get('member').get('user').get('id')
                user = bank.get_user(user_id)

                # parse command
                command = body.get('data').get('name')
                options = body.get('data').get('options')
                if len(options) > 0 and command == "bb":
                    option = options[0].get('name')
                    if option == "bank":
                        paycheck_message = ""
                        time_diff = datetime.datetime.now() - user.last_paycheck
                        if time_diff >= PAYCHECK_FREQUENCY:
                            user.balance += PAYCHECK
                            user.last_paycheck = datetime.datetime.now()
                            paycheck_message = f"Added daily paycheck: +${PAYCHECK}"
                        else:
                            paycheck_message = f"{humanize.naturaldelta(PAYCHECK_FREQUENCY - time_diff)} until next paycheck"

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": f"Balance: ${user.balance}\n{paycheck_message}",
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    elif option == "bet":
                        against = None
                        arbitrator = None
                        amount = None
                        condition = None
                        options = options[0].get('options')
                        for option in options:
                            option_name = option.get('name')
                            match option_name:
                                case 'against':
                                    against = option.get('value')
                                case 'arbitrator':
                                    arbitrator = option.get('value')
                                case 'amount':
                                    amount = option.get('value')
                                case 'condition':
                                    condition = option.get('value')

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": bank.make_bet(user, against, arbitrator, amount, condition),
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    else:
                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": f"Failed to parse command. Got unknown option: {option}",
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                else:
                    # wrong command or no arguments
                    resp = {
                        "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                        "data": {
                            "tts": False,
                            "content": f"Failed to parse command. Unknown command or no arguments given: {command}",
                            "embeds": [],
                            "allowed_mentions": []
                        }
                    };
        except Exception as e:
            resp = {
                "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                "data": {
                    "tts": False,
                    "content": f"Error running command.\nCommand: {command}\nOptions: {options}\nError: {e}",
                    "embeds": [],
                    "allowed_mentions": []
                }
            };

    print(f"response {resp}") #debug print
    return resp;

def init_server(server: str):
    os.makedirs(f"{BANK_DIR}/{server}", exist_ok=True)

def server_file(server: str):
    return f"{BANK_DIR}/{server}";

def format_user(id: str):
    return f"<@{id}>"

@dataclass
class User(JSONWizard):
    id: str
    balance: int
    last_paycheck: datetime.datetime

    def fmt(self):
        return format_user(self.id)
    
    # @staticmethod
    # def from_json(json):
    #     return User(json.get('id'), json.get('balance'), last_paycheck=json.get('last_paycheck'))

@dataclass
class Bet(JSONWizard):
    p1: str
    p2: str
    arbitrator: str
    amount: int
    condition: str
    start_time: datetime.datetime
    # used once bet is in history
    end_time: datetime.datetime
    pending: bool
    p1_won: bool
    # @staticmethod

    # def from_json(json):
    #     return Bet(p1=json.get('p1'),
    #                p2=json.get('p2'),
    #                arbitrator=json.get('arbitrator'),
    #                amount=json.get('amount'),
    #                condition=json.get('condition'),
    #                start_time=json.get('start_time'),
    #                end_time=json.get('end_time'),
    #                p1_won=json.get('p1_won'))

    def describe_now(self):
        return f"{format_user(self.p1)} bets ${self.amount} against {format_user(self.p2)}\n" + \
               f"Condition: {self.condition}"
    def describe_history(self):
        winner = format_user(self.p1) if self.p1_won else format_user(self.p2)
        loser = format_user(self.p2) if self.p1_won else format_user(self.p1)
        return f"Bet: {winner} won {self.amount} from {loser}\n" \
               f"Condition: {self.condition}"

@dataclass
class Bank(JSONWizard):
    users: Dict[str, User]
    current_bets: list[Bet]
    history: list[Bet]

    def get_bet(self: Bank, p1: str, p2: str):
        for bet in self.current_bets:
            if (bet.p1 == p1 and bet.p2 == p2) or (bet.p1 == p2 and bet.p2 == p1):
                return bet
        return None

    def get_user(self, user_id: str):
        if user_id not in self.users.keys():
            user = User(id=user_id,
                        balance=0,
                        last_paycheck=datetime.datetime.min)
            self.users[user_id] = user
            return user
        else:
            return self.users[user_id]

    def make_bet(self: Bank, user: User, against: str | None, arbitrator: str | None, amount: int | None, condition: str | None):
        if against == None:
            return "Error: 'against' is invalid"
        if arbitrator == None:
            return "Error: 'arbitrator' is invalid"
        if amount == None:
            return "Error: 'amount' is invalid"
        if condition == None:
            return "Error: 'condition' is invalid"
        start_time = datetime.datetime.now()
        end_time = datetime.datetime.max
        bet = Bet(p1=user.id,
                  p2=against,
                  arbitrator=arbitrator,
                  amount=amount,
                  condition=condition,
                  start_time=start_time,
                  end_time=end_time,
                  p1_won=False,
                  pending=True)
        other = self.get_user(against)
        fail_msg = "Failed to place bet"
        if self.get_bet(user.id, against) != None:
            return f"{fail_msg}\n{bet.describe_now()}\nCannot place bet. There is already a bet between {user.fmt()} and {other.fmt()}"
        if user.balance < amount and other.balance < amount:
            return f"{fail_msg}\n{bet.describe_now()}\nNeither {user.fmt()} nor {other.fmt()} has enough money for this bet!"
        if user.balance < amount:
            return f"{fail_msg}\n{bet.describe_now()}\n{user.fmt()} does not have enough money for this bet!"
        if other.balance < amount:
            return f"{fail_msg}\n{bet.describe_now()}\n{other.fmt()} does not have enough money for this bet!"
        self.current_bets.append(bet)
        return f"{user.fmt()} has requested a bet!\n{bet.describe_now()}\nWill {other.fmt()} accept?"

@contextmanager
def server(server_id: str):
    os.makedirs(BANK_DIR, exist_ok=True)
    with open(server_file(server_id), "a+", encoding='utf-8') as file:
        if file.tell() > 0:
            file.seek(0, SEEK_SET)
            bank = cast(Bank, Bank.from_json(file.read()))
        else:
            bank = Bank({}, [], [])

        try:
            yield bank
        except Exception as e:
            # don't write to file
            raise e
        else:
            file.seek(0, SEEK_SET)
            file.truncate(0)
            file.write(bank.to_json())
            file.flush()

