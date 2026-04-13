from pathlib import Path
import json, sqlite3, urllib.request, datetime as dt

base = Path.home() / 'alkaline-business'
store = Path(__file__).resolve().parents[1]
config = json.loads((store / 'config' / 'payment.json').read_text(encoding='utf-8'))
log = base / 'logs' / 'activity.log'

def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': '0', 'method': method}
    if params is not None:
        payload['params'] = params
    req = urllib.request.Request(config['rpc_url'], data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))

bal = rpc('get_balance')
transfers = rpc('get_transfers', {'in': True, 'pool': True})
conn = sqlite3.connect(base / 'db' / 'earnings.sqlite3')
cur = conn.cursor()
count = 0
for tx in transfers.get('result', {}).get('in', []):
    txid = tx.get('txid') or tx.get('tx_hash')
    amt = float(tx.get('amount', 0)) / 1e12 if tx.get('amount') else 0.0
    if not txid:
        continue
    cur.execute('SELECT 1 FROM payment_events WHERE txid=?', (txid,))
    if cur.fetchone():
        continue
    payload = json.dumps(tx)
    cur.execute('INSERT INTO payment_events(stream_name, txid, amount_xmr, height, payload) VALUES(?,?,?,?,?)', ('Data Products', txid, amt, tx.get('height'), payload))
    cur.execute('INSERT INTO earnings(stream_name, event_date, amount, currency, note) VALUES(?,?,?,?,?)', ('Data Products', dt.date.today().isoformat(), amt, 'XMR', f'Payment detected {txid}'))
    count += 1
conn.commit(); conn.close()
msg = f"[{dt.datetime.now().isoformat(timespec='seconds')}] payment_watch: balance={bal.get('result', {}).get('balance')} detected={count}"
log.open('a', encoding='utf-8').write(msg + '\n')
print(msg)
