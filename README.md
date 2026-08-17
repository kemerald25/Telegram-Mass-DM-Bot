# Telegram-Mass-DM-Sender-Bot Available At Free

<h3 align="center">Termux Installation</h3>

First Open Termux App

```
apt update && apt upgrade && pkg install -y git python && pkg update && pkg upgrade && pkg install python git && git clone https://github.com/saifalisew1508/Telegram-Mass-DM-Bot.git
```

```
cd Telegram-Mass-DM-Bot && ls
```

```
pip install -r requirements.txt
```

```
python3 -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```


```
ls
```

Installation done

Now run script and Inpur your API_HASH and API_ID, Phone_Number

```
python3 setup.py
```

Edit message file and input your message you want to send users in dm

```
nano Message.txt
```



And then Adding Members By using 

```
python3 run.py
```


<h3 align="center">Visitors Counts👀</h3>
<a href="https://github.com/saifalisew1508/Telegram-Mass-DM-Bot"><img alt="Cute Count" src="https://count.getloli.com/get/@Telegram-Mass-DM-Bot?theme=rule34" /></a>

---

## Windows RDP Deployment (Running 24/7)

Follow this step-by-step guide to set up the bot on your remote Windows desktop connection so it runs continuously, even after you shut down your local PC.

### Step 1: Transfer the Project to the RDP Server
1. Select the `Telegram-Mass-DM-Bot` folder on your local PC and copy it (`Ctrl + C`).
2. Open your Windows Remote Desktop (RDP) connection.
3. Paste the folder onto the desktop or in the `Documents` directory on the remote machine (`Ctrl + V`).

### Step 2: Install Python on the Remote Server
1. On the remote server, open a web browser and download the latest stable release of **Python 3.12** (recommended for package compatibility).
2. Run the installer.
3. **Important:** Check the box at the bottom that says **"Add Python to PATH"** before clicking install.

### Step 3: Install Dependencies
1. Open **Windows PowerShell** on the remote server.
2. Navigate to your project directory:
   ```powershell
   cd C:\Users\Administrator\Documents\Telegram-Mass-DM-Bot
   ```
3. Install the required Python packages.
   * *If using Python 3.12 (Recommended):*
     ```powershell
     pip install -r requirements.txt
     ```
   * *If using Python 3.13 or newer (requires a workaround for removed standard modules):*
     ```powershell
     pip install standard-imghdr
     pip install attrs==21.4.0 markdown-it-py==2.2.0 pyaes==1.6.1 pyasn1==0.4.8 rsa==4.7.2 Telethon==1.27.0
     ```

### Step 4: Run Setup and Authorize Accounts
1. Run the setup script to register the Telegram accounts:
   ```powershell
   python setup.py
   ```
2. Select **Option 1** to add a new account.
3. Enter your account API ID, API Hash, and phone number, and input the code Telegram sends to authorization.
4. When finished, select **Option 4** to exit.

### Step 5: Configure Message Content
1. Open `message.txt` in Notepad on the remote server.
2. Input the message template you wish to send.
3. Save and close the file.

### Step 6: Start the Campaign
1. Run the runner script:
   ```powershell
   python run.py
   ```
2. Choose your option (e.g., Option 1 to send messages to scraped members).
3. Input the parameters when prompted (e.g., base delay timing and rotation limit).

### Step 7: Keep the Script Running After Disconnecting
To ensure the bot continues running after you close RDP and shut down your local PC:
1. **Leave the PowerShell window open and running.**
2. **Do not click "Sign Out" or "Log Off"** in the Windows start menu of the remote server.
3. Simply close the Remote Desktop Connection window by clicking the **`X`** button on the blue connection bar at the top of your screen. 
4. The user session will remain active on the remote server, keeping the bot running indefinitely.

---

## Conceptual Reference: Proxies & Rate-Limiting in Python

This section explains the general networking concepts behind routing connections through proxies and managing request rates in Python applications.

### 1. How Proxies Work (SOCKS5 vs. HTTP)
When a script makes an API connection, it defaults to using your machine's public IP address. To route traffic through a different IP address, applications use proxies:

* **HTTP Proxies:** Designed only for web traffic (HTTP/HTTPS protocols). They inspect and forward web page requests.
* **SOCKS5 Proxies:** Operate at the transport layer (TCP/UDP). Because they do not interpret the application data, they can route any protocol—including database connections, custom API protocols (like MTProto), and secure socket connections.

In Python, libraries like `PySocks` are used to intercept the default networking sockets and route the TCP streams through a specified proxy server before reaching the destination host.

### 2. Rate Limiting and Request Throttling
API providers enforce rate limits to protect server resources and prevent abuse. When building network clients, developers implement throttling to stay within these limits:

* **Fixed Delays:** Introducing a static wait time (e.g., `time.sleep(30)`) between requests to prevent overwhelming the server.
* **Jitter (Randomized Delays):** Adding a small random variance to the delay (e.g., `30 seconds +/- 15%`) to distribute traffic and prevent burst patterns.
* **Connection Rotation:** Distributing API requests across different client sessions or endpoints to avoid hitting rate limits on a single connection.
