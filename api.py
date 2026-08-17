#!/usr/bin/env python3
"""
Telegram Mass DM Bot — Web Dashboard API
Run: python api.py
Access: http://your-droplet-ip:8000
"""

from flask import Flask, request, jsonify, session, Response, send_from_directory
from telethon.sync import TelegramClient
from telethon.tl.types import InputPeerUser
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError,
    PeerFloodError, UserDeactivatedError, AuthKeyUnregisteredError, FloodWaitError
)
import socks
import asyncio
import threading
import queue
import os
import csv
import json
import random
import time
import functools
from datetime import timedelta

# ─────────────────────────────────────────────────────────────
# App configuration
# ─────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='dashboard', static_url_path='/dashboard')
app.secret_key = 'tgdmbot-sk-7X2pL9mK4nQ8rJ5vC'
app.permanent_session_lifetime = timedelta(hours=24)

# ════ CHANGE THESE BEFORE DEPLOYING ════
DASHBOARD_USER = "admin"
DASHBOARD_PASS = "dmbot2024!"
PORT           = 8000
# ════════════════════════════════════════

DEFAULT_PROXY_FILE = 'proxy_default.json'

# ─────────────────────────────────────────────────────────────
# In-memory state
# ─────────────────────────────────────────────────────────────
_auth_pending  = {}          # phone -> {client, phone_code_hash, api_id, api_hash}
_auth_lock     = threading.Lock()

_campaign_thread = None
_stop_event      = threading.Event()
_log_queue       = queue.Queue(maxsize=2000)

campaign_status = {
    'running': False, 'sent': 0,
    'total': 0, 'current_account': '',
}

def check_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

# ─────────────────────────────────────────────────────────────
# Auth decorator
# ─────────────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────────────────────
# Auth routes
# ─────────────────────────────────────────────────────────────
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    if data.get('username') == DASHBOARD_USER and data.get('password') == DASHBOARD_PASS:
        session.permanent = True
        session['logged_in'] = True
        return jsonify({'ok': True})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/auth/me')
def auth_me():
    return jsonify({'logged_in': bool(session.get('logged_in'))})

# ─────────────────────────────────────────────────────────────
# Static — serve dashboard
# ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('dashboard', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('dashboard', path)

# ─────────────────────────────────────────────────────────────
# Proxy helpers
# ─────────────────────────────────────────────────────────────
_PROXY_MAP = {'socks5': socks.SOCKS5, 'socks4': socks.SOCKS4, 'http': socks.HTTP}

def build_proxy_arg(acc):
    host = acc.get('proxy_host', '').strip()
    if not host:
        return None
    pt   = _PROXY_MAP.get(acc.get('proxy_type', 'socks5').lower(), socks.SOCKS5)
    port = int(acc.get('proxy_port', 1080)) if str(acc.get('proxy_port', '')).isdigit() else 1080
    user = acc.get('proxy_user', '').strip() or None
    pwd  = acc.get('proxy_pass', '').strip() or None
    return (pt, host, port, True, user, pwd)

def proxy_display(acc):
    host = acc.get('proxy_host', '').strip()
    if not host:
        return None
    return f"{acc.get('proxy_type','').upper()} {host}:{acc.get('proxy_port','')}"

# ─────────────────────────────────────────────────────────────
# Account helpers
# ─────────────────────────────────────────────────────────────
def load_accounts():
    accounts = []
    if not os.path.exists('user_auth.csv'):
        return accounts
    with open('user_auth.csv', 'r', encoding='UTF-8') as f:
        reader = csv.reader(f, delimiter=',', lineterminator='\n')
        try:
            header = next(reader)
            old = (header == ['api_id', 'api_hash', 'phone'])
            new = (header == ['api_id', 'api_hash', 'phone', 'proxy_type',
                               'proxy_host', 'proxy_port', 'proxy_user', 'proxy_pass'])
            if old or new:
                for row in reader:
                    if len(row) >= 3:
                        acc = {'api_id': row[0], 'api_hash': row[1], 'phone': row[2],
                               'proxy_type': '', 'proxy_host': '', 'proxy_port': '',
                               'proxy_user': '', 'proxy_pass': ''}
                        if len(row) >= 8:
                            acc.update({'proxy_type': row[3], 'proxy_host': row[4],
                                        'proxy_port': row[5], 'proxy_user': row[6], 'proxy_pass': row[7]})
                        accounts.append(acc)
        except StopIteration:
            pass
    return accounts

def save_accounts(accounts):
    with open('user_auth.csv', 'w', encoding='UTF-8', newline='') as f:
        writer = csv.writer(f, delimiter=',', lineterminator='\n')
        writer.writerow(['api_id', 'api_hash', 'phone', 'proxy_type',
                         'proxy_host', 'proxy_port', 'proxy_user', 'proxy_pass'])
        for a in accounts:
            writer.writerow([a.get('api_id',''), a.get('api_hash',''), a.get('phone',''),
                             a.get('proxy_type',''), a.get('proxy_host',''), a.get('proxy_port',''),
                             a.get('proxy_user',''), a.get('proxy_pass','')])

def load_default_proxy():
    if os.path.exists(DEFAULT_PROXY_FILE):
        try:
            with open(DEFAULT_PROXY_FILE, 'r') as f:
                d = json.load(f)
            return d if d.get('proxy_host') else None
        except Exception:
            pass
    return None

def save_default_proxy(proxy):
    if proxy.get('proxy_host'):
        with open(DEFAULT_PROXY_FILE, 'w') as f:
            json.dump(proxy, f, indent=2)

# ─────────────────────────────────────────────────────────────
# Message helpers
# ─────────────────────────────────────────────────────────────
def load_message_templates():
    if not os.path.exists('message.txt'):
        return []
    with open('message.txt', 'r', encoding='UTF-8') as f:
        content = f.read()
    return [t.strip() for t in content.split('---') if t.strip()]

def format_message(templates, name):
    template = random.choice(templates)
    for fmt in [lambda t: t.format(name=name), lambda t: t.format(name)]:
        try:
            return fmt(template)
        except Exception:
            pass
    return template

# ─────────────────────────────────────────────────────────────
# Accounts API
# ─────────────────────────────────────────────────────────────
@app.route('/api/accounts', methods=['GET'])
@login_required
def get_accounts():
    return jsonify({'accounts': [
        {'phone': a['phone'], 'api_id': a['api_id'],
         'proxy': proxy_display(a),
         'has_session': os.path.exists(f"session_{a['phone']}.session")}
        for a in load_accounts()
    ]})

@app.route('/api/accounts/start-auth', methods=['POST'])
@login_required
def start_auth():
    check_loop()
    data     = request.json or {}
    phone    = data.get('phone', '').strip()
    api_id   = data.get('api_id', '').strip()
    api_hash = data.get('api_hash', '').strip()

    if not all([phone, api_id, api_hash]):
        return jsonify({'error': 'phone, api_id, and api_hash are required'}), 400
    try:
        api_id_int = int(api_id)
    except ValueError:
        return jsonify({'error': 'api_id must be a number'}), 400

    if any(a['phone'] == phone for a in load_accounts()):
        return jsonify({'error': f'{phone} is already registered'}), 409

    # Clean up stale pending auth
    with _auth_lock:
        if phone in _auth_pending:
            try:
                _auth_pending[phone]['client'].disconnect()
            except Exception:
                pass
            del _auth_pending[phone]

    try:
        client = TelegramClient(f'session_{phone}', api_id_int, api_hash)
        client.connect()
        sent = client.send_code_request(phone)
        with _auth_lock:
            _auth_pending[phone] = {
                'client': client,
                'phone_code_hash': sent.phone_code_hash,
                'api_id': api_id,
                'api_hash': api_hash,
            }
        return jsonify({'ok': True, 'message': f'OTP sent to {phone}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/verify-otp', methods=['POST'])
@login_required
def verify_otp():
    check_loop()
    data  = request.json or {}
    phone = data.get('phone', '').strip()
    code  = data.get('code', '').strip()

    with _auth_lock:
        pending = _auth_pending.get(phone)
    if not pending:
        return jsonify({'error': 'No pending auth for this phone. Start auth first.'}), 400
    if not code:
        return jsonify({'error': 'code is required'}), 400

    try:
        pending['client'].sign_in(phone, code, phone_code_hash=pending['phone_code_hash'])
        _finish_auth(phone, pending)
        return jsonify({'ok': True, 'message': f'{phone} registered successfully!'})
    except SessionPasswordNeededError:
        return jsonify({'ok': False, 'needs_2fa': True, 'message': '2FA password required'})
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accounts/verify-2fa', methods=['POST'])
@login_required
def verify_2fa():
    check_loop()
    data     = request.json or {}
    phone    = data.get('phone', '').strip()
    password = data.get('password', '').strip()

    with _auth_lock:
        pending = _auth_pending.get(phone)
    if not pending:
        return jsonify({'error': 'No pending auth for this phone.'}), 400

    try:
        pending['client'].sign_in(password=password)
        _finish_auth(phone, pending)
        return jsonify({'ok': True, 'message': f'{phone} registered with 2FA!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _finish_auth(phone, pending):
    accounts = load_accounts()
    default  = load_default_proxy() or {}
    new_acc  = {'api_id': pending['api_id'], 'api_hash': pending['api_hash'], 'phone': phone,
                 'proxy_type': default.get('proxy_type', ''), 'proxy_host': default.get('proxy_host', ''),
                 'proxy_port': default.get('proxy_port', ''), 'proxy_user': default.get('proxy_user', ''),
                 'proxy_pass': default.get('proxy_pass', '')}
    accounts.append(new_acc)
    save_accounts(accounts)
    try:
        pending['client'].disconnect()
    except Exception:
        pass
    with _auth_lock:
        _auth_pending.pop(phone, None)

@app.route('/api/accounts/<phone>', methods=['DELETE'])
@login_required
def delete_account(phone):
    accounts = load_accounts()
    new_list = [a for a in accounts if a['phone'] != phone]
    if len(new_list) == len(accounts):
        return jsonify({'error': 'Account not found'}), 404
    save_accounts(new_list)
    sf = f'session_{phone}.session'
    if os.path.exists(sf):
        try:
            os.remove(sf)
        except Exception:
            pass
    return jsonify({'ok': True, 'message': f'{phone} removed'})

# ─────────────────────────────────────────────────────────────
# Proxy API
# ─────────────────────────────────────────────────────────────
@app.route('/api/proxy/default', methods=['GET'])
@login_required
def get_default_proxy():
    return jsonify({'proxy': load_default_proxy()})

@app.route('/api/proxy/set-all', methods=['POST'])
@login_required
def set_proxy_all():
    data  = request.json or {}
    proxy = {
        'proxy_type': data.get('proxy_type', 'socks5'),
        'proxy_host': data.get('proxy_host', '').strip(),
        'proxy_port': str(data.get('proxy_port', '')),
        'proxy_user': data.get('proxy_user', '').strip(),
        'proxy_pass': data.get('proxy_pass', '').strip(),
    }
    if not proxy['proxy_host']:
        return jsonify({'error': 'proxy_host is required'}), 400
    accounts = load_accounts()
    for acc in accounts:
        acc.update(proxy)
    save_accounts(accounts)
    save_default_proxy(proxy)
    return jsonify({'ok': True, 'message': f'Proxy applied to {len(accounts)} account(s)'})

@app.route('/api/proxy/<phone>', methods=['DELETE'])
@login_required
def remove_proxy(phone):
    accounts = load_accounts()
    found = False
    for acc in accounts:
        if acc['phone'] == phone:
            acc.update({'proxy_type': '', 'proxy_host': '', 'proxy_port': '',
                        'proxy_user': '', 'proxy_pass': ''})
            found = True
    if not found:
        return jsonify({'error': 'Account not found'}), 404
    save_accounts(accounts)
    return jsonify({'ok': True})

# ─────────────────────────────────────────────────────────────
# Message API
# ─────────────────────────────────────────────────────────────
@app.route('/api/message', methods=['GET'])
@login_required
def get_message():
    raw = ''
    if os.path.exists('message.txt'):
        with open('message.txt', 'r', encoding='UTF-8') as f:
            raw = f.read()
    templates = [t.strip() for t in raw.split('---') if t.strip()]
    return jsonify({'raw': raw, 'count': len(templates)})

@app.route('/api/message', methods=['POST'])
@login_required
def save_message():
    data = request.json or {}
    raw  = data.get('raw', '')
    if not raw.strip():
        return jsonify({'error': 'Message cannot be empty'}), 400
    with open('message.txt', 'w', encoding='UTF-8') as f:
        f.write(raw)
    count = len([t for t in raw.split('---') if t.strip()])
    return jsonify({'ok': True, 'count': count})

# ─────────────────────────────────────────────────────────────
# Members API
# ─────────────────────────────────────────────────────────────
@app.route('/api/members', methods=['GET'])
@login_required
def get_members():
    if not os.path.exists('members.csv'):
        return jsonify({'count': 0, 'sample': []})
    sample = []
    count  = 0
    with open('members.csv', encoding='UTF-8') as f:
        rows = list(csv.reader(f))
    if len(rows) > 1:
        count  = len(rows) - 1
        for row in rows[1:6]:
            if len(row) >= 4:
                sample.append({'name': row[3], 'username': row[0]})
    return jsonify({'count': count, 'sample': sample})

# ─────────────────────────────────────────────────────────────
# Campaign runner (background thread)
# ─────────────────────────────────────────────────────────────
def _clog(msg):
    try:
        _log_queue.put_nowait(msg)
    except queue.Full:
        pass

def _run_campaign(config):
    global campaign_status
    check_loop()

    sleep_time = config.get('sleep_time', 60)
    max_dms    = config.get('max_dms', 2)
    mode       = config.get('mode', 1)

    _clog('═' * 55)
    _clog(f'[Campaign] Starting | delay: {sleep_time}s | max DMs/acc: {max_dms} | mode: {mode}')
    _clog('═' * 55)

    accounts  = load_accounts()
    templates = load_message_templates()

    if not accounts:
        _clog('[Error] No accounts registered.'); campaign_status['running'] = False; return
    if not templates:
        _clog('[Error] message.txt is empty.'); campaign_status['running'] = False; return
    if not os.path.exists('members.csv'):
        _clog('[Error] members.csv not found.'); campaign_status['running'] = False; return

    users = []
    with open('members.csv', encoding='UTF-8') as f:
        rows = csv.reader(f, delimiter=',', lineterminator='\n')
        next(rows, None)
        for row in rows:
            if len(row) >= 4:
                try:
                    users.append({'username': row[0], 'id': int(row[1]),
                                  'access_hash': int(row[2]), 'name': row[3]})
                except Exception:
                    pass

    if not users:
        _clog('[Error] No valid users in members.csv.'); campaign_status['running'] = False; return

    sent_history = set()
    if os.path.exists('sent_history.txt'):
        with open('sent_history.txt', 'r', encoding='UTF-8') as f:
            for line in f:
                try:
                    sent_history.add(int(line.strip()))
                except Exception:
                    pass

    campaign_status.update({'total': len(users), 'sent': 0})
    _clog(f'[Campaign] {len(users)} total | {len(sent_history)} already sent | '
          f'{len(accounts)} accounts | {len(templates)} template(s)')

    available        = list(accounts)
    current_idx      = 0
    client           = None
    sent_this_sess   = 0
    session_limit    = max(1, random.randint(max(1, max_dms - 1), max_dms + 2))

    def connect_next(proactive=True):
        nonlocal current_idx, client, sent_this_sess, session_limit
        if client:
            try: client.disconnect()
            except Exception: pass
            client = None

        if available:
            if not proactive:
                removed = available.pop(current_idx)
                _clog(f'[Rotation] Removed {removed["phone"]} from pool')
            else:
                current_idx = (current_idx + 1) % len(available) if available else 0

        while available:
            current_idx = current_idx % len(available)
            acc = available[current_idx]

            jitter = random.uniform(2, 8)
            _clog(f'[Jitter] Waiting {jitter:.1f}s...')
            time.sleep(jitter)
            if _stop_event.is_set():
                return None

            proxy = build_proxy_arg(acc)
            pdisp = proxy_display(acc) or 'direct'
            _clog(f'[Rotation] Connecting {acc["phone"]} | {pdisp}')
            campaign_status['current_account'] = acc['phone']

            try:
                c = TelegramClient(f'session_{acc["phone"]}', int(acc['api_id']), acc['api_hash'],
                                   proxy=proxy, device_model='Windows Desktop',
                                   system_version='Windows 11', app_version='4.8.4')
                c.connect()
                if not c.is_user_authorized():
                    _clog(f'[Rotation] {acc["phone"]} not authorized. Removing.')
                    c.disconnect()
                    available.pop(current_idx)
                    continue
                client         = c
                sent_this_sess = 0
                session_limit  = max(1, random.randint(max(1, max_dms - 1), max_dms + 2))
                _clog(f'[Rotation] Connected: {acc["phone"]} | Session limit: {session_limit} DMs')
                return client
            except Exception as e:
                _clog(f'[Rotation] Failed {acc["phone"]}: {e}')
                try: c.disconnect()
                except Exception: pass
                available.pop(current_idx)

        return None

    client = connect_next(proactive=True)
    if not client:
        _clog('[Error] No authorized accounts available.')
        campaign_status['running'] = False
        return

    for user in users:
        if _stop_event.is_set():
            _clog('[Campaign] Stop requested. Halting.')
            break

        if user['id'] in sent_history:
            continue

        if sent_this_sess >= session_limit:
            if len(available) > 1:
                _clog(f'[Rotate] Session limit {session_limit} reached. Switching account...')
                client = connect_next(proactive=True)
                if not client:
                    _clog('[Error] No more accounts available.')
                    break
            else:
                session_limit = max(1, random.randint(max(1, max_dms - 1), max_dms + 2))
                sent_this_sess = 0
                _clog(f'[Proactive] Single account. New limit: {session_limit}')

        sent = False
        while not sent:
            if _stop_event.is_set() or not client:
                break
            try:
                if mode == 2:
                    if not user['username']:
                        _clog(f'[Skip] {user["name"]} — no username'); sent = True; continue
                    receiver = client.get_input_entity(user['username'])
                else:
                    receiver = InputPeerUser(user['id'], user['access_hash'])

                msg = format_message(templates, user['name'])
                acc_phone = available[current_idx]['phone']
                _clog(f'[Send] → {user["name"]} ({user["id"]}) via {acc_phone}')
                client.send_message(receiver, msg)

                with open('sent_history.txt', 'a', encoding='UTF-8') as f:
                    f.write(f"{user['id']}\n")
                sent_history.add(user['id'])
                sent_this_sess       += 1
                campaign_status['sent'] += 1
                sent = True

                # Human pause with ±30% variance + 8% chance of long pause
                delay = sleep_time * random.uniform(0.70, 1.30)
                if random.random() < 0.08:
                    extra = random.uniform(30, 120)
                    _clog(f'[Human Pause] Extra {extra:.0f}s break...')
                    delay += extra
                _clog(f'[Wait] {delay:.1f}s before next message...')

                elapsed = 0
                while elapsed < delay and not _stop_event.is_set():
                    time.sleep(min(1, delay - elapsed))
                    elapsed += 1

            except PeerFloodError:
                _clog(f'[Error] PeerFloodError. Rotating...')
                client = connect_next(proactive=False)
            except FloodWaitError as e:
                _clog(f'[Error] FloodWait {e.seconds}s. Rotating...')
                client = connect_next(proactive=False)
            except (UserDeactivatedError, AuthKeyUnregisteredError) as e:
                _clog(f'[Error] Account banned: {e}. Rotating...')
                client = connect_next(proactive=False)
            except ValueError as e:
                _clog(f'[Skip] Cannot resolve {user["name"]}: {e}'); sent = True
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ['deactivated', 'unregistered', 'auth', 'flood']):
                    _clog(f'[Error] Account error: {e}. Rotating...')
                    client = connect_next(proactive=False)
                else:
                    _clog(f'[Skip] Send failed for {user["name"]}: {e}'); sent = True

    if client:
        try: client.disconnect()
        except Exception: pass

    _clog('═' * 55)
    _clog(f'[Campaign] Completed. Total sent: {campaign_status["sent"]}')
    _clog('═' * 55)
    campaign_status['running'] = False

# ─────────────────────────────────────────────────────────────
# Campaign API
# ─────────────────────────────────────────────────────────────
@app.route('/api/campaign/status', methods=['GET'])
@login_required
def get_campaign_status():
    return jsonify(campaign_status)

@app.route('/api/campaign/start', methods=['POST'])
@login_required
def start_campaign():
    global _campaign_thread
    if campaign_status['running']:
        return jsonify({'error': 'Campaign already running'}), 409

    data   = request.json or {}
    config = {
        'sleep_time': int(data.get('sleep_time', 60)),
        'max_dms':    int(data.get('max_dms', 2)),
        'mode':       int(data.get('mode', 1)),
    }

    _stop_event.clear()
    while not _log_queue.empty():
        try: _log_queue.get_nowait()
        except Exception: break

    campaign_status.update({'running': True, 'sent': 0, 'total': 0, 'current_account': ''})
    _campaign_thread = threading.Thread(target=_run_campaign, args=(config,), daemon=True)
    _campaign_thread.start()
    return jsonify({'ok': True, 'message': 'Campaign started'})

@app.route('/api/campaign/stop', methods=['POST'])
@login_required
def stop_campaign():
    _stop_event.set()
    campaign_status['running'] = False
    return jsonify({'ok': True, 'message': 'Stop signal sent'})

@app.route('/api/campaign/logs')
@login_required
def campaign_logs():
    def generate():
        while True:
            try:
                msg = _log_queue.get(timeout=1)
                yield f"data: {json.dumps({'msg': msg})}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs('dashboard', exist_ok=True)
    print(f"""
╔════════════════════════════════════════════╗
║    Telegram DM Bot — Web Dashboard         ║
╠════════════════════════════════════════════╣
║  URL  :  http://0.0.0.0:{PORT}              ║
║  User :  {DASHBOARD_USER:<34}║
╚════════════════════════════════════════════╝
""")
    app.run(host='0.0.0.0', port=PORT, threaded=True, debug=False)
