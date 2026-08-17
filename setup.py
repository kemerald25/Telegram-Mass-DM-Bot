import os
import sys
import csv
import glob
import json
from telethon.sync import TelegramClient

VALID_PROXY_TYPES = ['socks5', 'socks4', 'http']
DEFAULT_PROXY_FILE = 'proxy_default.json'

def save_default_proxy(proxy_details):
    """Persist a proxy config as the default for future new accounts."""
    if proxy_details.get('proxy_host'):
        with open(DEFAULT_PROXY_FILE, 'w', encoding='UTF-8') as f:
            json.dump(proxy_details, f, indent=2)

def load_default_proxy():
    """Load the saved default proxy config, or return None if not set."""
    if os.path.exists(DEFAULT_PROXY_FILE):
        try:
            with open(DEFAULT_PROXY_FILE, 'r', encoding='UTF-8') as f:
                data = json.load(f)
            if data.get('proxy_host'):
                return data
        except Exception:
            pass
    return None

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_accounts():
    accounts = []
    if os.path.exists("user_auth.csv"):
        with open("user_auth.csv", "r", encoding='UTF-8') as f:
            reader = csv.reader(f, delimiter=",", lineterminator="\n")
            try:
                header = next(reader)
                # Support both old (3-col) and new (8-col) schema
                old_schema = header == ['api_id', 'api_hash', 'phone']
                new_schema = header == ['api_id', 'api_hash', 'phone',
                                        'proxy_type', 'proxy_host', 'proxy_port',
                                        'proxy_user', 'proxy_pass']
                if old_schema or new_schema:
                    for row in reader:
                        if len(row) >= 3:
                            acc = {
                                'api_id': row[0],
                                'api_hash': row[1],
                                'phone': row[2],
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
            except StopIteration:
                pass
    return accounts

def save_accounts(accounts):
    with open("user_auth.csv", "w", encoding='UTF-8', newline='') as f:
        writer = csv.writer(f, delimiter=",", lineterminator="\n")
        writer.writerow(['api_id', 'api_hash', 'phone',
                         'proxy_type', 'proxy_host', 'proxy_port',
                         'proxy_user', 'proxy_pass'])
        for acc in accounts:
            writer.writerow([
                acc['api_id'], acc['api_hash'], acc['phone'],
                acc.get('proxy_type', ''),
                acc.get('proxy_host', ''),
                acc.get('proxy_port', ''),
                acc.get('proxy_user', ''),
                acc.get('proxy_pass', ''),
            ])

def prompt_proxy_details(offer_default=False):
    """
    Interactively ask the user for proxy details.
    If offer_default=True and a default proxy is saved, offer to reuse it.
    Returns dict of proxy fields.
    """
    default = load_default_proxy()

    if offer_default and default:
        ptype = default['proxy_type'].upper()
        host  = default['proxy_host']
        port  = default['proxy_port']
        user  = default.get('proxy_user', '')
        auth  = f" | user: {user}" if user else ""
        print(f"\n--- Proxy Configuration ---")
        print(f"Saved default proxy: {ptype} {host}:{port}{auth}")
        use_default = input("Use saved proxy for this account? (y/n) [default: y]: ").strip().lower()
        if use_default in ('', 'y', 'yes'):
            print(f"[OK] Using saved {ptype} proxy.")
            return default
        # User said no — fall through to manual entry

    print("\n--- Proxy Configuration (optional) ---")
    print("Proxy types supported: socks5, socks4, http")
    print("Leave proxy host blank to skip (direct connection, no proxy).")
    proxy_host = input("Proxy host (e.g. p.webshare.io): ").strip()
    if not proxy_host:
        return {'proxy_type': '', 'proxy_host': '', 'proxy_port': '',
                'proxy_user': '', 'proxy_pass': ''}

    proxy_type = input("Proxy type (socks5 / socks4 / http) [default: socks5]: ").strip().lower()
    if proxy_type not in VALID_PROXY_TYPES:
        print(f"  Invalid type '{proxy_type}', defaulting to socks5.")
        proxy_type = 'socks5'

    proxy_port = input("Proxy port (e.g. 1080): ").strip()
    if not proxy_port.isdigit():
        print("  Invalid port, defaulting to 1080.")
        proxy_port = '1080'

    proxy_user = input("Proxy username (leave blank if none): ").strip()
    proxy_pass = ''
    if proxy_user:
        proxy_pass = input("Proxy password: ").strip()

    result = {
        'proxy_type': proxy_type,
        'proxy_host': proxy_host,
        'proxy_port': proxy_port,
        'proxy_user': proxy_user,
        'proxy_pass': proxy_pass,
    }
    # Auto-save as the new default
    save_default_proxy(result)
    return result

def register_account():
    clear_screen()
    print("=== Register a New Telegram Account ===")
    
    api_id_str = input("Enter your API ID: ").strip()
    if not api_id_str.isdigit():
        print("Error: API ID must be a number.")
        input("Press Enter to return...")
        return
    api_id = int(api_id_str)
    
    api_hash = input("Enter your API Hash: ").strip()
    if not api_hash:
        print("Error: API Hash cannot be empty.")
        input("Press Enter to return...")
        return
        
    phone = input("Enter your Phone Number (with country code, e.g., +1234567890): ").strip()
    if not phone.startswith('+'):
        print("Warning: Phone number should ideally start with '+' (e.g., +1234567890).")
        confirm = input("Do you want to continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            return
            
    # Load existing accounts to check for duplicate phone numbers
    accounts = load_accounts()
    for acc in accounts:
        if acc['phone'] == phone:
            print(f"Error: Account with phone number {phone} is already registered.")
            input("Press Enter to return...")
            return

    # Proxy configuration — auto-offer the saved default if one exists
    proxy_details = prompt_proxy_details(offer_default=True)
    if proxy_details.get('proxy_host'):
        save_default_proxy(proxy_details)
            
    print("\nAttempting to connect and authorize account...")
    print("Telegram will send a code to your phone number via Telegram or SMS.")
    
    session_name = f"session_{phone}"
    
    try:
        client = TelegramClient(session_name, api_id, api_hash)
        client.start(phone)
        
        if client.is_user_authorized():
            print("\nAuthorization successful!")
            me = client.get_me()
            name = (f"{me.first_name or ''} {me.last_name or ''}").strip() or me.username or phone
            print(f"Logged in as: {name}")
            
            new_acc = {
                'api_id': str(api_id),
                'api_hash': api_hash,
                'phone': phone,
            }
            new_acc.update(proxy_details)
            accounts.append(new_acc)
            save_accounts(accounts)
            print("Account details saved successfully!")
        else:
            print("\nFailed to authorize the account.")
            
        client.disconnect()
    except Exception as e:
        print(f"\nAn error occurred during authentication: {e}")
        
    input("\nPress Enter to return to menu...")

def list_accounts():
    clear_screen()
    print("=== Registered Accounts ===")
    accounts = load_accounts()
    if not accounts:
        print("No accounts registered yet.")
    else:
        for idx, acc in enumerate(accounts):
            proxy_info = "No proxy"
            if acc.get('proxy_host'):
                masked = f"{acc['proxy_type'].upper()} {acc['proxy_host']}:{acc['proxy_port']}"
                if acc.get('proxy_user'):
                    masked += f" (auth: {acc['proxy_user']}:***)"
                proxy_info = masked
            print(f"{idx + 1}. Phone: {acc['phone']} | API ID: {acc['api_id']} | Proxy: {proxy_info}")
    input("\nPress Enter to return to menu...")

def manage_proxies():
    clear_screen()
    print("=== Manage Proxies ===")
    accounts = load_accounts()
    if not accounts:
        print("No accounts registered. Add accounts first.")
        input("Press Enter to return...")
        return

    print("Accounts:\n")
    for idx, acc in enumerate(accounts):
        proxy_info = "No proxy"
        if acc.get('proxy_host'):
            proxy_info = f"{acc['proxy_type'].upper()} {acc['proxy_host']}:{acc['proxy_port']}"
        print(f"  {idx + 1}. {acc['phone']} — {proxy_info}")

    print()
    print("Actions:")
    print("  1. Set / update proxy for ONE account")
    print("  2. Remove proxy from ONE account")
    print("  3. Set SAME proxy for ALL accounts at once")
    print("  4. Remove proxy from ALL accounts")
    print("  0. Cancel")
    print()
    action = input("Choice: ").strip()

    if action == '1':
        try:
            choice = int(input("Account number: "))
        except ValueError:
            return
        if choice < 1 or choice > len(accounts):
            print("Invalid selection.")
            input("Press Enter to return...")
            return
        proxy_details = prompt_proxy_details()
        if not proxy_details['proxy_host']:
            print("No host entered — proxy unchanged.")
        else:
            accounts[choice - 1].update(proxy_details)
            save_accounts(accounts)
            save_default_proxy(proxy_details)
            ptype = proxy_details['proxy_type'].upper()
            print(f"\n[OK] Proxy set for {accounts[choice - 1]['phone']}: "
                  f"{ptype} {proxy_details['proxy_host']}:{proxy_details['proxy_port']}")

    elif action == '2':
        try:
            choice = int(input("Account number: "))
        except ValueError:
            return
        if choice < 1 or choice > len(accounts):
            print("Invalid selection.")
            input("Press Enter to return...")
            return
        accounts[choice - 1].update({
            'proxy_type': '', 'proxy_host': '', 'proxy_port': '',
            'proxy_user': '', 'proxy_pass': ''
        })
        save_accounts(accounts)
        print(f"\n[OK] Proxy removed from {accounts[choice - 1]['phone']}.")

    elif action == '3':
        print(f"\nThis will set the SAME proxy for all {len(accounts)} account(s).")
        proxy_details = prompt_proxy_details()
        if not proxy_details['proxy_host']:
            print("No host entered — nothing changed.")
        else:
            for acc in accounts:
                acc.update(proxy_details)
            save_accounts(accounts)
            save_default_proxy(proxy_details)
            ptype = proxy_details['proxy_type'].upper()
            print(f"\n[OK] Proxy set for ALL {len(accounts)} account(s): "
                  f"{ptype} {proxy_details['proxy_host']}:{proxy_details['proxy_port']}")

    elif action == '4':
        confirm = input(f"Remove proxy from all {len(accounts)} account(s)? (yes/no): ").strip().lower()
        if confirm == 'yes':
            for acc in accounts:
                acc.update({
                    'proxy_type': '', 'proxy_host': '', 'proxy_port': '',
                    'proxy_user': '', 'proxy_pass': ''
                })
            save_accounts(accounts)
            print(f"\n[OK] Proxy removed from all {len(accounts)} account(s).")
        else:
            print("Cancelled.")
    else:
        print("Cancelled.")

    input("\nPress Enter to return to menu...")

def clear_all_accounts():
    clear_screen()
    print("=== Clear All Accounts ===")
    confirm = input("Are you sure you want to clear all accounts and session files? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if os.path.exists("user_auth.csv"):
            os.remove("user_auth.csv")
            print("Removed user_auth.csv")
            
        session_files = glob.glob("session_*.session")
        session_files.extend(glob.glob("anon*.session"))
        for sf in session_files:
            try:
                os.remove(sf)
                print(f"Removed session file: {sf}")
            except Exception as e:
                print(f"Failed to remove {sf}: {e}")
                
        print("\nAll accounts and session files have been cleared.")
    else:
        print("\nOperation cancelled.")
    input("\nPress Enter to return to menu...")

def main():
    while True:
        clear_screen()
        print("=======================================")
        print("   Telegram Mass DM Bot - Setup Menu   ")
        print("=======================================")
        print("1. Add a new account")
        print("2. List registered accounts")
        print("3. Manage proxies")
        print("4. Clear all accounts")
        print("5. Exit")
        print("=======================================")
        
        choice = input("Enter your choice (1-5): ").strip()
        if choice == '1':
            register_account()
        elif choice == '2':
            list_accounts()
        elif choice == '3':
            manage_proxies()
        elif choice == '4':
            clear_all_accounts()
        elif choice == '5':
            print("Exiting Setup. You can now run run.py.")
            sys.exit()
        else:
            print("Invalid choice. Press Enter to retry...")
            input()

if __name__ == "__main__":
    main()