import os
import sys
import csv
import glob
from telethon.sync import TelegramClient

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_accounts():
    accounts = []
    if os.path.exists("user_auth.csv"):
        with open("user_auth.csv", "r", encoding='UTF-8') as f:
            reader = csv.reader(f, delimiter=",", lineterminator="\n")
            try:
                header = next(reader)
                # Verify header format
                if header == ['api_id', 'api_hash', 'phone']:
                    for row in reader:
                        if len(row) == 3:
                            accounts.append({
                                'api_id': row[0],
                                'api_hash': row[1],
                                'phone': row[2]
                            })
            except StopIteration:
                pass
    return accounts

def save_accounts(accounts):
    with open("user_auth.csv", "w", encoding='UTF-8', newline='') as f:
        writer = csv.writer(f, delimiter=",", lineterminator="\n")
        writer.writerow(['api_id', 'api_hash', 'phone'])
        for acc in accounts:
            writer.writerow([acc['api_id'], acc['api_hash'], acc['phone']])

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
            
    print("\nAttempting to connect and authorize account...")
    print("Telegram will send a code to your phone number via Telegram or SMS.")
    
    # We use a session file specific to this phone number
    session_name = f"session_{phone}"
    
    # Run the interactive telethon client authentication
    try:
        client = TelegramClient(session_name, api_id, api_hash)
        client.start(phone)
        
        # Verify authorization status
        if client.is_user_authorized():
            print("\nAuthorization successful!")
            me = client.get_me()
            name = (f"{me.first_name or ''} {me.last_name or ''}").strip() or me.username or phone
            print(f"Logged in as: {name}")
            
            # Save account details
            accounts.append({
                'api_id': str(api_id),
                'api_hash': api_hash,
                'phone': phone
            })
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
            print(f"{idx + 1}. Phone: {acc['phone']} (API ID: {acc['api_id']})")
    input("\nPress Enter to return to menu...")

def clear_all_accounts():
    clear_screen()
    print("=== Clear All Accounts ===")
    confirm = input("Are you sure you want to clear all accounts and session files? (yes/no): ").strip().lower()
    if confirm == 'yes':
        # Remove CSV file
        if os.path.exists("user_auth.csv"):
            os.remove("user_auth.csv")
            print("Removed user_auth.csv")
            
        # Remove session files
        session_files = glob.glob("session_*.session")
        session_files.extend(glob.glob("anon*.session")) # also clean up old default session files
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
        print("3. Clear all accounts")
        print("4. Exit")
        print("=======================================")
        
        choice = input("Enter your choice (1-4): ").strip()
        if choice == '1':
            register_account()
        elif choice == '2':
            list_accounts()
        elif choice == '3':
            clear_all_accounts()
        elif choice == '4':
            print("Exiting Setup. You can now run run.py.")
            sys.exit()
        else:
            print("Invalid choice. Press Enter to retry...")
            input()

if __name__ == "__main__":
    main()