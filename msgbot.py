from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerUser
from telethon.errors import (
    PeerFloodError,
    UserDeactivatedError,
    AuthKeyUnregisteredError,
    FloodWaitError
)
import socks
import sys
import os
import csv
import random
import time

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# ---------------------------------------------------------------------------
# Proxy helpers
# ---------------------------------------------------------------------------

_PROXY_TYPE_MAP = {
    'socks5': socks.SOCKS5,
    'socks4': socks.SOCKS4,
    'http':   socks.HTTP,
}

def build_proxy_arg(acc):
    """
    Build the proxy tuple expected by Telethon from an account dict.
    Returns None if the account has no proxy configured.

    For rotating proxy APIs, each new TelegramClient connection to the
    same endpoint gets a fresh egress IP from the provider's pool.
    """
    proxy_host = acc.get('proxy_host', '').strip()
    if not proxy_host:
        return None

    proxy_type_str = acc.get('proxy_type', 'socks5').lower().strip()
    proxy_type = _PROXY_TYPE_MAP.get(proxy_type_str, socks.SOCKS5)

    try:
        proxy_port = int(acc.get('proxy_port', 1080))
    except (ValueError, TypeError):
        proxy_port = 1080

    proxy_user = acc.get('proxy_user', '').strip() or None
    proxy_pass = acc.get('proxy_pass', '').strip() or None

    # rdns=True: DNS resolution happens on the proxy server (required for rotating proxies)
    return (proxy_type, proxy_host, proxy_port, True, proxy_user, proxy_pass)

def proxy_display(acc):
    """Return a human-readable proxy string (password masked)."""
    host = acc.get('proxy_host', '').strip()
    if not host:
        return "direct (no proxy)"
    ptype = acc.get('proxy_type', 'socks5').upper()
    port  = acc.get('proxy_port', '')
    user  = acc.get('proxy_user', '').strip()
    auth  = f" | auth: {user}:***" if user else ""
    return f"{ptype} {host}:{port}{auth} [rotating]"

# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def load_messages(filepath):
    """
    Load message templates from a file.
    Templates are separated by a line containing only '---'.
    Returns a list of template strings (at least one).
    """
    with open(filepath, "r", encoding='UTF-8') as f:
        content = f.read()
    templates = [t.strip() for t in content.split('---') if t.strip()]
    if not templates:
        raise ValueError("message.txt is empty or has no valid templates.")
    return templates

def format_message(templates, name):
    """
    Pick a random template and substitute the recipient's name.
    Supports both {name} and {0} / {} placeholder styles.
    """
    template = random.choice(templates)
    try:
        return template.format(name=name)
    except (KeyError, IndexError):
        pass
    try:
        return template.format(name)
    except (KeyError, IndexError):
        pass
    return template  # no placeholder — send as-is

def human_pause(base_delay):
    """
    Sleep for base_delay with ±30% variance.
    8% chance of an extra 'human' pause (30–120 extra seconds).
    """
    variance     = random.uniform(0.70, 1.30)
    actual_delay = base_delay * variance

    if random.random() < 0.08:
        extra = random.uniform(30, 120)
        print(f"[Human Pause] Taking an extra {extra:.0f}s break (simulating human behaviour)...")
        actual_delay += extra

    print(f"Waiting {actual_delay:.1f} seconds before next message...")
    time.sleep(actual_delay)
    return actual_delay

# ---------------------------------------------------------------------------
# Account / history helpers
# ---------------------------------------------------------------------------

def load_accounts():
    accounts = []
    if os.path.exists("user_auth.csv"):
        with open("user_auth.csv", "r", encoding='UTF-8') as f:
            reader = csv.reader(f, delimiter=",", lineterminator="\n")
            try:
                header = next(reader)
                old_schema = header == ['api_id', 'api_hash', 'phone']
                new_schema = header == ['api_id', 'api_hash', 'phone',
                                        'proxy_type', 'proxy_host', 'proxy_port',
                                        'proxy_user', 'proxy_pass']
                if old_schema or new_schema:
                    for row in reader:
                        if len(row) >= 3:
                            acc = {
                                'api_id':     int(row[0]),
                                'api_hash':   row[1],
                                'phone':      row[2],
                                'proxy_type': '',
                                'proxy_host': '',
                                'proxy_port': '',
                                'proxy_user': '',
                                'proxy_pass': '',
                            }
                            if len(row) >= 8:
                                acc['proxy_type'] = row[3].lower().strip()
                                acc['proxy_host'] = row[4].strip()
                                acc['proxy_port'] = row[5].strip()
                                acc['proxy_user'] = row[6].strip()
                                acc['proxy_pass'] = row[7].strip()
                            accounts.append(acc)
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

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
            next(rows, None)  # skip header
            for row in rows:
                if len(row) >= 4:
                    users.append({
                        'username':    row[0],
                        'id':          int(row[1]),
                        'access_hash': int(row[2]),
                        'name':        row[3]
                    })
        except Exception as e:
            print(f"Error reading {input_file}: {e}")
            sys.exit(1)

    if not users:
        print(f"No users found in {input_file}.")
        sys.exit(0)

    print(f"\nLoaded {len(accounts)} account(s):")
    for idx, acc in enumerate(accounts):
        print(f"  {idx + 1}. {acc['phone']} | Proxy: {proxy_display(acc)}")
    print()

    try:
        SLEEP_TIME          = int(input("Enter Delay Timing For Per Message Sending : "))
        MAX_DMS_PER_ACCOUNT = int(input("Enter max DMs per account before proactive rotation (default 5): "))
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

    try:
        message_templates = load_messages("message.txt")
    except Exception as e:
        print(f"Error loading message.txt: {e}")
        sys.exit(1)

    print(f"Loaded {len(message_templates)} message template(s). Will rotate randomly per recipient.")

    sent_history = load_sent_history()
    
    available_accounts             = list(accounts)
    current_account_index          = 0
    client                         = None
    sent_count_for_current_account = 0
    session_limit = max(1, random.randint(
        max(1, MAX_DMS_PER_ACCOUNT - 1),
        MAX_DMS_PER_ACCOUNT + 2
    ))

    def switch_client(proactive=True):
        nonlocal current_account_index, client, sent_count_for_current_account
        
        # 1. Disconnect current client
        if client:
            try:
                client.disconnect()
            except:
                pass
            client = None

        # 2. Adjust pool and index
        if available_accounts:
            if not proactive:
                failed_acc = available_accounts.pop(current_account_index)
                print(f"[Rotation] Removed failed/banned account {failed_acc['phone']} from rotation pool.")
            else:
                current_account_index = (current_account_index + 1) % len(available_accounts)

        # 3. Connect to next available account
        while available_accounts:
            current_account_index = current_account_index % len(available_accounts)
            acc      = available_accounts[current_account_index]
            phone    = acc['phone']
            api_id   = acc['api_id']
            api_hash = acc['api_hash']
            proxy    = build_proxy_arg(acc)

            # Pre-connection jitter
            jitter = random.uniform(2, 8)
            print(f"[Jitter] Waiting {jitter:.1f}s before connecting new session...")
            time.sleep(jitter)

            print(f"\n[Rotation] Connecting to account: {phone} ({current_account_index + 1}/{len(available_accounts)})...")
            print(f"[Proxy]    {proxy_display(acc)}")
            
            c = TelegramClient(
                f"session_{phone}",
                api_id,
                api_hash,
                proxy=proxy,
                device_model="Windows Desktop",
                system_version="Windows 11",
                app_version="4.8.4"
            )
            try:
                c.connect()
                if not c.is_user_authorized():
                    print(f"[Rotation] Account {phone} is not authorized. Removing from pool...")
                    c.disconnect()
                    available_accounts.pop(current_account_index)
                    continue
                
                client = c
                sent_count_for_current_account = 0
                session_limit = max(1, random.randint(
                    max(1, MAX_DMS_PER_ACCOUNT - 1),
                    MAX_DMS_PER_ACCOUNT + 2
                ))
                print(f"[Rotation] Successfully connected using {phone}! Session limit: {session_limit} DMs")
                return client
            except Exception as e:
                print(f"[Rotation] Failed to connect using {phone}: {e}. Removing from pool...")
                try:
                    c.disconnect()
                except:
                    pass
                available_accounts.pop(current_account_index)
                
        return None

    client = switch_client(proactive=True)
    if not client:
        print("\nNo authorized accounts available. Exiting.")
        sys.exit(1)

    print(f"\nStarting DM Campaign. Total users: {len(users)}")
    print(f"Skipping users already found in sent_history.txt ({len(sent_history)} total).")

    for user in users:
        user_id           = user['id']
        user_name_str     = user['username']
        user_display_name = user['name']

        if user_id in sent_history:
            continue

        if sent_count_for_current_account >= session_limit:
            if len(available_accounts) > 1:
                print(f"\n[Proactive Rotate] Reached session limit of {session_limit} DMs for account "
                      f"{available_accounts[current_account_index]['phone']}. Rotating to new IP...")
                client = switch_client(proactive=True)
                if not client:
                    print("\n[Out of Accounts] No more active accounts available.")
                    break
            else:
                session_limit = max(1, random.randint(
                    max(1, MAX_DMS_PER_ACCOUNT - 1),
                    MAX_DMS_PER_ACCOUNT + 2
                ))
                print(f"\n[Proactive Check] Only one account remains. Resetting session limit to {session_limit}.")
                sent_count_for_current_account = 0

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

                formatted_msg = format_message(message_templates, user_display_name)

                print(f"Sending message to {user_display_name} ({user_id}) "
                      f"using account {available_accounts[current_account_index]['phone']} "
                      f"| Proxy: {proxy_display(available_accounts[current_account_index])}...")
                client.send_message(receiver, formatted_msg)
                
                save_sent_history(user_id)
                sent_history.add(user_id)
                sent_count_for_current_account += 1
                sent = True

                human_pause(SLEEP_TIME)

            except PeerFloodError:
                print(f"[Error] Account {available_accounts[current_account_index]['phone']} "
                      f"got PeerFloodError. Rotating to new IP...")
                client = switch_client(proactive=False)
            except FloodWaitError as fwe:
                print(f"[Error] Account {available_accounts[current_account_index]['phone']} "
                      f"got FloodWaitError (Must wait {fwe.seconds}s). Rotating to new IP...")
                client = switch_client(proactive=False)
            except (UserDeactivatedError, AuthKeyUnregisteredError) as ban_err:
                print(f"[Error] Account {available_accounts[current_account_index]['phone']} "
                      f"is banned or deactivated: {ban_err}. Rotating...")
                client = switch_client(proactive=False)
            except ValueError as val_err:
                print(f"[Target Error] Cannot resolve entity for {user_display_name}: {val_err}")
                print("Skipping user.")
                sent = True
            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ["deactivated", "unregistered", "auth", "flood"]):
                    print(f"[Error] Account {available_accounts[current_account_index]['phone']} "
                          f"encountered account error: {e}. Rotating to new IP...")
                    client = switch_client(proactive=False)
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
