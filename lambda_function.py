from __future__ import annotations
import datetime
import pytz
from typing import cast
from contextlib import contextmanager
from io import SEEK_SET, TextIOWrapper
from typing import Dict
from public_key import PUBLIC_KEY, BANK_DIR, VERSION, VERSION_MAX_LENGTH, TIMEZONE
from dataclasses import dataclass
from dataclass_wizard import JSONWizard
import json
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
                        time_diff = user.last_paycheck - get_prev_midnight()
                        if time_diff < datetime.timedelta(0):
                            user.balance += PAYCHECK
                            user.last_paycheck = datetime.datetime.now()
                            paycheck_message = f"Added daily paycheck: +${PAYCHECK}"
                        else:
                            paycheck_message = f"{humanize.precisedelta(get_next_midnight() - datetime.datetime.now(), format='%0.f')} until next paycheck"

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
                                "content": bank.cmd_make_bet(user, against, arbitrator, amount, condition),
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    elif option == "accept":
                        against = None
                        options = options[0].get('options')
                        for option in options:
                            option_name = option.get('name')
                            match option_name:
                                case 'against':
                                    against = option.get('value')

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": bank.cmd_accept_bet(user, against),
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    elif option == "reject":
                        against = None
                        options = options[0].get('options')
                        for option in options:
                            option_name = option.get('name')
                            match option_name:
                                case 'against':
                                    against = option.get('value')

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": bank.cmd_reject_bet(user, against),
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    elif option == "decide":
                        victor = None
                        loser = None
                        options = options[0].get('options')
                        for option in options:
                            option_name = option.get('name')
                            match option_name:
                                case 'victor':
                                    victor = option.get('value')
                                case 'loser':
                                    loser = option.get('value')

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": bank.cmd_decide_bet(user, victor, loser),
                                "embeds": [],
                                "allowed_mentions": []
                            }
                        };
                    elif option == "cancel":
                        against = None
                        options = options[0].get('options')
                        for option in options:
                            option_name = option.get('name')
                            match option_name:
                                case 'against':
                                    against = option.get('value')

                        resp = {
                            "type": RESPONSE_TYPES['MESSAGE_WITH_SOURCE'],
                            "data": {
                                "tts": False,
                                "content": bank.cmd_cancel_bet(user, against),
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
    p1_won: bool # else p2 won
    pending: bool
    rejected: bool
    p1_cancel: bool
    p2_cancel: bool
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

    def cancel_bet(self, a: str, b: str):
        for i in range(len(self.current_bets)):
            bet = self.current_bets[i]
            # if this bet pertains to a and b
            if bet.p1 == a and bet.p2 == b or bet.p2 == a and bet.p1 == b:
                bet.end_time = datetime.datetime.now()
                self.get_user(bet.p1).balance += bet.amount
                refund_text = f"${bet.amount} has been refunded to {format_user(bet.p1)}"
                if not bet.pending:
                    self.get_user(bet.p2).balance += bet.amount
                    refund_text += f"\n${bet.amount} has been refunded to {format_user(bet.p2)}"
                self.history.append(bet)
                del self.current_bets[i]
                return refund_text
        raise Exception(f"Error: canceled nonexistent bet between {format_user(a)} and {format_user(b)}")

    def cmd_make_bet(self: Bank, user: User, against: str | None, arbitrator: str | None, amount: int | None, condition: str | None):
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
                  pending=True,
                  rejected=False,
                  p1_cancel=False,
                  p2_cancel=False)
        other = self.get_user(against)
        fail_msg = "Failed to place bet"
        if amount <= 0:
            return "Bet must be nonnegative"
        if self.get_bet(user.id, against) != None:
            return f"Cannot place bet. There is already a bet between {user.fmt()} and {other.fmt()}"
        if user.balance < amount and other.balance < amount:
            return f"Cannot place bet. Neither {user.fmt()} nor {other.fmt()} has enough money: {amount}"
        if user.balance < amount:
            return f"{fail_msg}\n{bet.describe_now()}\n{user.fmt()} does not have enough money: {user.balance}"
        if other.balance < amount:
            return f"{fail_msg}\n{bet.describe_now()}\n{other.fmt()} does not have enough money: {other.balance}"
        self.current_bets.append(bet)
        user.balance -= amount
        return f"{bet.describe_now()}\n${amount} has been subtracted from {user.fmt()}'s account\nWill {other.fmt()} accept?"

    def cmd_reject_bet(self: Bank, user: User, against: str | None):
        if against == None:
            return "Error: 'against' is invalid"
        for i in range(len(self.current_bets)):
            bet = self.current_bets[i]
            # if this bet pertains to user and against
            if bet.p1 == user.id and bet.p2 == against or bet.p2 == user.id and bet.p1 == against:
                if not bet.pending:
                    # interpret this as a cancelation request
                    return self.cmd_cancel_bet(user, against)
                elif bet.p2 == user.id:
                    bet.p2_cancel = True
                    refund_text = self.cancel_bet(user.id, against)
                    return f"{user.fmt()} rejected the request with {format_user(against)}\n{refund_text}"
                else:
                    # if pending and is p1
                    # interpret this as a cancelation request
                    return self.cmd_cancel_bet(user, against)
        return f"There is no bet between you and {format_user(against)}"

    def cmd_cancel_bet(self: Bank, user: User, against: str | None):
        if against == None:
            return "Error: 'against' is invalid"
        for i in range(len(self.current_bets)):
            bet = self.current_bets[i]
            # if this bet pertains to user and against
            if bet.p1 == user.id and bet.p2 == against or bet.p2 == user.id and bet.p1 == against:
                if bet.p1 == user.id:
                    bet.p1_cancel = True
                if bet.p2 == user.id:
                    bet.p2_cancel = True
                refund_text = ""
                if bet.pending or bet.p1_cancel and bet.p2_cancel:
                    refund_text = self.cancel_bet(user.id, against)
                if bet.pending:
                    return f"{user.fmt()} cancelled a bet request with {format_user(against)}\n{refund_text}"
                elif bet.p1_cancel and bet.p2_cancel:
                    # if bet is already made but other agreed to cancel
                    return f"{user.fmt()} agreed to cancel a bet with {format_user(against)}\n{refund_text}"
                else:
                    #if not pending and one of the two hasn't canceled
                    return f"{user.fmt()} is requesting to cancel a bet with {format_user(against)}"
        return f"There is no bet between you and {format_user(against)}"

    def cmd_accept_bet(self: Bank, user: User, against: str | None):
        if against == None:
            return "Error: 'against' is invalid"
        for i in range(len(self.current_bets)):
            bet = self.current_bets[i]
            # if user this bet pertains to user and against
            if bet.p1 == user.id and bet.p2 == against or bet.p2 == user.id and bet.p1 == against:
                if not bet.pending:
                    return f"Bet with {format_user(against)} is already accepted"
                elif bet.p2 == user.id:
                    # is p2 and bet is pending
                    bet.pending = False
                    bet.start_time = datetime.datetime.now()
                    user.balance -= bet.amount
                    return f"Bet with {format_user(against)} accepted!\n" +\
                            f"${bet.amount} has been subtracted from {user.fmt()}'s account\n" +\
                            f"Bet info:\n{bet.describe_now()}"
                else:
                    # is p1 and bet is pending
                    return f"Waiting for {format_user(against)} to accept"
        return f"There is no bet between you and {format_user(against)}"

    def cmd_decide_bet(self: Bank, user: User, victor: str | None, loser: str | None):
        if victor == None:
            return "Error: 'victor' is invalid"
        if loser == None:
            return "Error: 'loser' is invalid"
        for i in range(len(self.current_bets)):
            bet = self.current_bets[i]
            # if this bet pertains to user and against
            if bet.p1 == victor and bet.p2 == loser or bet.p2 == victor and bet.p1 == loser:
                if user.id != bet.arbitrator:
                    return f"You are not the arbitrator for this bet"
                elif bet.pending:
                    return f"You must wait until this bet is accepted before arbitrating"
                else:
                    victor_user = self.get_user(victor)
                    bet.end_time = datetime.datetime.now()
                    if bet.p1 == victor:
                        bet.p1_won = True
                    else:
                        bet.p1_won = False
                    victor_user.balance += bet.amount * 2
                    awarded_text = f"${bet.amount * 2} has been awarded to {format_user(victor)}"
                    self.history.append(bet)
                    del self.current_bets[i]
                    return f"{format_user(bet.arbitrator)} has decided that {format_user(victor)} " +\
                            f"has won their bet with {format_user(loser)}!\nCondition: {bet.condition}\n{awarded_text}"
        return f"There is no bet between {format_user(victor)} and {format_user(loser)}"

@contextmanager
def server(server_id: str):
    os.makedirs(BANK_DIR, exist_ok=True)
    with open(server_file(server_id), "a+", encoding='utf-8') as file:
        if file.tell() > 0:
            file.seek(0, SEEK_SET)
            version = read_version(file)
            print(f"Found bank with version {version}")
            if version != "empty":
                json = fix_bank_json(version, file.read())
                bank = cast(Bank, Bank.from_json(json))
            else:
                bank = Bank({}, [], [])
        else:
            print("No bank found")
            bank = Bank({}, [], [])

        try:
            yield bank
        except Exception as e:
            # don't write to file
            raise e
        else:
            file.seek(0, SEEK_SET)
            file.truncate(0)
            file.write(VERSION + '\n')
            file.write(bank.to_json())
            file.flush()

def read_version(file: TextIOWrapper):
    s = ""
    null_char = False
    for _ in range(VERSION_MAX_LENGTH):
        next = file.read(1)
        if len(next) == 0:
            return "empty"
        if next == "\n":
            null_char = True
            break
        s += next
    if null_char:
        return s
    file.seek(0, SEEK_SET)
    return "first"

def fix_bank_json(version: str, s: str):
    if version == VERSION:
        return s
    else:
        obj = json.loads(s)
        print(f"Updating {version} -> {VERSION}")
        match version:
            case 'first':
                for bet in obj.get('currentBets'):
                    bet['pending'] = True
                for bet in obj.get('history'):
                    bet['pending'] = False
            case '1.0':
                for bet in obj.get('currentBets'):
                    bet['p1_cancel'] = False
                    bet['p2_cancel'] = False
                for bet in obj.get('history'):
                    bet['p1_cancel'] = False
                    bet['p2_cancel'] = False
            case '1.1':
                for bet in obj.get('currentBets'):
                    bet['rejected'] = False
                for bet in obj.get('history'):
                    bet['rejected'] = False
        return json.dumps(obj)

# def test():
#     # with open("test", "a+", encoding="utf-8") as file:
#     #     file.seek(0, SEEK_SET)
#     #     version = read_version(file)
#     #     print(f"Found version {version}")
#     #     other = file.read()
#     #     if len(other) == 0:
#     #         print("Writing other")
#     #         other = "asdjifajosdif"
#     #     print(f"Other: {other}")
# 
#     #     file.seek(0, SEEK_SET)
#     #     file.truncate(0)
#     #     file.write('2.0' + '\n')
#     #     file.write(other)
#     #     file.flush()
#     global BANK_DIR
#     BANK_DIR = "."
#     with server('test') as bank:
#         print(bank)
# 
# test()

def get_next_midnight():
    today = datetime.datetime.now(pytz.timezone("America/New_York")) \
                .replace(hour=0,minute=0,second=0,microsecond=0)
    date = today.date() + datetime.timedelta(days=1)
    dt = datetime.datetime.combine(date=date, time=today.time(), tzinfo=today.tzinfo)
    return dt.astimezone(pytz.utc).replace(tzinfo=None)
def get_prev_midnight():
    return datetime.datetime.now(pytz.timezone("America/New_York")) \
            .replace(hour=0,minute=0,second=0,microsecond=0) \
            .astimezone(pytz.utc) \
            .replace(tzinfo=None)
