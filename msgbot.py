from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerUser
from telethon.errors import (
    PeerFloodError,
    UserDeactivatedError,
    AuthKeyUnregisteredError,
    FloodWaitError
)
import sys
import os
import csv
import random
import time

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_accounts():
    accounts = []
    if os.path.exists("user_auth.csv"):
        with open("user_auth.csv", "r", encoding='UTF-8') as f:
            reader = csv.reader(f, delimiter=",", lineterminator="\n")
            try:
                header = next(reader)
                if header == ['api_id', 'api_hash', 'phone']:
                    for row in reader:
                        if len(row) == 3:
                            accounts.append({
                                'api_id': int(row[0]),
                                'api_hash': row[1],
                                'phone': row[2]
                            })
            except Exception as e:
                print(f"Error reading user_auth.csv: {e}")
    return accounts

def load_sent_history():
    sent_ids = set()
    if os.path.exists("sent_history.txt"):
        with open("sent_history.txt", "r", encoding='UTF-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        sent_ids.add(int(line))
                    except ValueError:
                        pass
    return sent_ids

def save_sent_history(user_id):
    with open("sent_history.txt", "a", encoding='UTF-8') as f:
        f.write(f"{user_id}\n")

def main():
    clear_screen()
    print("=======================================")
    print("      Telegram Standalone DM Bot       ")
    print("=======================================")

    accounts = load_accounts()
    if not accounts:
        print("ERROR: No registered accounts found in user_auth.csv.")
        print("Please run 'python setup.py' first to add at least one Telegram account.")
        sys.exit(1)

    # Determine input file from CLI arguments or default to members.csv
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "members.csv"
        print(f"No input file specified. Defaulting to '{input_file}'")

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)

    users = []
    with open(input_file, encoding='UTF-8') as f:
        rows = csv.reader(f, delimiter=",", lineterminator="\n")
        try:
            next(rows, None) # skip header
            for row in rows:
                if len(row) >= 4:
                    users.append({
                        'username': row[0],
                        'id': int(row[1]),
                        'access_hash': int(row[2]),
                        'name': row[3]
                    })
        except Exception as e:
            print(f"Error reading {input_file}: {e}")
            sys.exit(1)

    if not users:
        print(f"No users found in {input_file}.")
        sys.exit(0)

    try:
        SLEEP_TIME = int(input("Enter Delay Timing For Per Message Sending : "))
        MAX_DMS_PER_ACCOUNT = int(input("Enter max DMs per account before proactive rotation: "))
        mode = int(input("Enter 1 to send by user ID or 2 to send by username: "))
        if mode not in [1, 2]:
            print("Invalid sending mode. Exiting.")
            sys.exit(1)
    except ValueError:
        print("Invalid input values. Exiting.")
        sys.exit(1)

    # Read message.txt
    if not os.path.exists("message.txt"):
        print("Error: message.txt not found. Create message.txt with your message template.")
        sys.exit(1)

    with open("message.txt", "r", encoding='UTF-8') as f:
        messages = "".join(f.readlines())

    if not messages.strip():
        print("Error: message.txt is empty.")
        sys.exit(1)

    sent_history = load_sent_history()
    
    active_idx = 0
    client = None
    sent_count_for_current_account = 0

    def get_next_client():
        nonlocal active_idx, client, sent_count_for_current_account
        if client:
            try:
                client.disconnect()
            except:
                pass
            client = None

        while active_idx < len(accounts):
            acc = accounts[active_idx]
            phone = acc['phone']
            api_id = acc['api_id']
            api_hash = acc['api_hash']
            print(f"\n[Rotation] Connecting to account: {phone}...")
            
            c = TelegramClient(
                f"session_{phone}", 
                api_id, 
                api_hash,
                device_model="Windows Desktop",
                system_version="Windows 11",
                app_version="4.8.4"
            )
            try:
                c.connect()
                if not c.is_user_authorized():
                    print(f"[Rotation] Account {phone} is not authorized. Skipping...")
                    c.disconnect()
                    active_idx += 1
                    continue
                
                client = c
                sent_count_for_current_account = 0
                print(f"[Rotation] Successfully connected using {phone}!")
                return client
            except Exception as e:
                print(f"[Rotation] Failed to connect using {phone}: {e}")
                active_idx += 1
                
        return None

    client = get_next_client()
    if not client:
        print("\nNo authorized accounts available. Exiting.")
        sys.exit(1)

    print(f"\nStarting DM Campaign. Total users: {len(users)}")
    print(f"Skipping users already found in sent_history.txt ({len(sent_history)} total).")

    for user in users:
        user_id = user['id']
        user_name_str = user['username']
        user_display_name = user['name']

        if user_id in sent_history:
            continue

        if sent_count_for_current_account >= MAX_DMS_PER_ACCOUNT:
            print(f"\n[Proactive Rotate] Reached max DM limit of {MAX_DMS_PER_ACCOUNT} for account {accounts[active_idx]['phone']}.")
            active_idx += 1
            client = get_next_client()
            if not client:
                print("\n[Out of Accounts] No more active accounts available.")
                break

        sent = False
        while not sent:
            if not client:
                break
                
            try:
                if mode == 2:
                    if not user_name_str:
                        print(f"Skipping {user_display_name} - no username set.")
                        sent = True
                        continue
                    receiver = client.get_input_entity(user_name_str)
                else:
                    receiver = InputPeerUser(user_id, user['access_hash'])

                formatted_msg = messages
                try:
                    formatted_msg = messages.format(user_display_name)
                except KeyError:
                    pass
                except IndexError:
                    pass

                print(f"Sending message to {user_display_name} ({user_id}) using account {accounts[active_idx]['phone']}...")
                client.send_message(receiver, formatted_msg)
                
                save_sent_history(user_id)
                sent_history.add(user_id)
                sent_count_for_current_account += 1
                sent = True

                variance = random.uniform(0.85, 1.15)
                actual_delay = SLEEP_TIME * variance
                print(f"Message sent successfully. Waiting {actual_delay:.2f} seconds...")
                time.sleep(actual_delay)

            except PeerFloodError:
                print(f"[Error] Account {accounts[active_idx]['phone']} got PeerFloodError.")
                print("Rotating to next account...")
                active_idx += 1
                client = get_next_client()
            except FloodWaitError as fwe:
                print(f"[Error] Account {accounts[active_idx]['phone']} got FloodWaitError (Must wait {fwe.seconds}s).")
                print("Rotating to next account...")
                active_idx += 1
                client = get_next_client()
            except (UserDeactivatedError, AuthKeyUnregisteredError) as ban_err:
                print(f"[Error] Account {accounts[active_idx]['phone']} is banned or deactivated: {ban_err}")
                print("Rotating to next account...")
                active_idx += 1
                client = get_next_client()
            except ValueError as val_err:
                print(f"[Target Error] Cannot resolve entity for {user_display_name}: {val_err}")
                print("Skipping user.")
                sent = True
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ["deactivated", "unregistered", "auth", "flood"]):
                    print(f"[Error] Account {accounts[active_idx]['phone']} encountered account error: {e}")
                    print("Rotating to next account...")
                    active_idx += 1
                    client = get_next_client()
                else:
                    print(f"[Send Error] Failed to send to {user_display_name}: {e}")
                    print("Skipping user and continuing...")
                    sent = True

    if client:
        try:
            client.disconnect()
        except:
            pass
    print("\nDM campaign execution completed.")

if __name__ == "__main__":
    main()
