from pathlib import Path
import json, sqlite3, urllib.request, datetime as dt

base = Path.home() / 'alkaline-business'
store = Path(__file__).resolve().parents[1]
config = json.loads((store / 'config' / 'payment.json').read_text(encoding='utf-8'))
log = base / 'logs' / 'activity.log'
DB_PATH = Path(config.get('database', str(base / 'db' / 'earnings.sqlite3')))


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': '0', 'method': method}
    if params is not None:
        payload['params'] = params
    req = urllib.request.Request(config['rpc_url'], data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))


def ensure_schema(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS earnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_name TEXT NOT NULL,
        event_date TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        currency TEXT NOT NULL DEFAULT 'USD',
        note TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS payment_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_name TEXT NOT NULL,
        txid TEXT,
        amount_xmr REAL,
        height INTEGER,
        payload TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_name TEXT NOT NULL,
        sku TEXT NOT NULL,
        customer_ref TEXT,
        amount_xmr REAL,
        amount_usd REAL,
        payment_txid TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )''')


bal = rpc('get_balance')
transfers = rpc('get_transfers', {'in': True, 'pool': True})
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
ensure_schema(cur)
count = 0
for tx in transfers.get('result', {}).get('in', []):
    txid = tx.get('txid') or tx.get('tx_hash')
    amt_atomic = tx.get('amount', 0) or 0
    amt = float(amt_atomic) / 1e12 if amt_atomic else 0.0
    if not txid:
        continue
    cur.execute('SELECT 1 FROM payment_events WHERE txid=?', (txid,))
    if cur.fetchone():
        continue
    payload = json.dumps(tx)
    cur.execute('INSERT INTO payment_events(stream_name, txid, amount_xmr, height, payload) VALUES(?,?,?,?,?)', ('Data Products', txid, amt, tx.get('height'), payload))
    cur.execute('INSERT INTO earnings(stream_name, event_date, amount, currency, note) VALUES(?,?,?,?,?)', ('Data Products', dt.date.today().isoformat(), amt, 'XMR', f'Payment detected {txid}'))
    # Match pending orders by amount.
    cur.execute('SELECT id, sku FROM orders WHERE stream_name=? AND status IN ("pending", "invoice_created") AND ABS(COALESCE(amount_xmr,0) - ?) < 0.00001 ORDER BY id DESC LIMIT 1', ('Data Products', amt))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE orders SET status=?, payment_txid=?, updated_at=datetime("now") WHERE id=?', ('paid', txid, row[0]))
    count += 1
conn.commit(); conn.close()
msg = f"[{dt.datetime.now().isoformat(timespec='seconds')}] payment_watch: balance={bal.get('result', {}).get('balance')} detected={count}"
log.open('a', encoding='utf-8').write(msg + '\n')
print(msg)
