from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import urllib.request

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
CONFIG = json.loads((BASE / 'config' / 'payment.json').read_text(encoding='utf-8'))
CATALOG = {item['sku']: item for item in json.loads((BASE / '_data' / 'catalog.json').read_text(encoding='utf-8'))}
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / 'activity.log'
DB_PATH = Path(CONFIG.get('database', str(ROOT / 'db' / 'earnings.sqlite3')))

STATUS_COPY = {
    'invoice_created': ('Invoice created', 'Waiting for payment.'),
    'payment_seen': ('Payment seen', 'The wallet saw the transfer; waiting for confirmations.'),
    'paid': ('Paid', 'Required confirmations reached. Delivery is being released.'),
    'delivered': ('Delivered', 'Download link unlocked.'),
}


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': '0', 'method': method}
    if params is not None:
        payload['params'] = params
    req = urllib.request.Request(
        CONFIG['rpc_url'],
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


def ensure_schema(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS earnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stream_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'USD',
            note TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stream_name TEXT NOT NULL,
            txid TEXT,
            amount_xmr REAL,
            height INTEGER,
            payload TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stream_name TEXT NOT NULL,
            sku TEXT NOT NULL,
            customer_ref TEXT,
            amount_xmr REAL,
            amount_usd REAL,
            payment_txid TEXT,
            status TEXT NOT NULL DEFAULT 'invoice_created',
            delivery_path TEXT,
            delivery_url TEXT,
            wallet_address TEXT,
            address_index INTEGER,
            confirmations_required INTEGER NOT NULL DEFAULT 10,
            confirmed_at TEXT,
            delivered_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    existing = {row[1] for row in cur.execute('PRAGMA table_info(orders)')}
    columns = {
        'delivery_path': 'TEXT',
        'delivery_url': 'TEXT',
        'wallet_address': 'TEXT',
        'address_index': 'INTEGER',
        'confirmations_required': 'INTEGER NOT NULL DEFAULT 10',
        'confirmed_at': 'TEXT',
        'delivered_at': 'TEXT',
    }
    for column, definition in columns.items():
        if column not in existing:
            cur.execute(f'ALTER TABLE orders ADD COLUMN {column} {definition}')


def order_status_line(status):
    return STATUS_COPY.get(status, (status.replace('_', ' ').title(), ''))


def render_order_page(order, item, invoice):
    status_title, status_note = order_status_line(order['status'])
    delivery_url = invoice.get('delivery_url') if order['status'] == 'delivered' else None
    delivery_block = (
        f'<p><a class="btn" href="{delivery_url}">Download your file</a></p>'
        if delivery_url
        else '<p class="muted">Delivery link will appear here automatically after payment confirms.</p>'
    )
    return f'''---
layout: default
title: Order #{order["id"]} — {item["name"]}
permalink: /orders/{order["id"]}/
---

<section class="hero">
  <p class="eyebrow">Order #{order["id"]}</p>
  <h1>{item["name"]}</h1>
  <p class="lead">{status_note}</p>
</section>

<section class="card">
  <div class="meta">
    <span class="pill">{item["format"]}</span>
    <span class="pill">{item["delivery_method"]}</span>
    <span class="pill">{status_title}</span>
  </div>
  <div class="order-card-head">
    <div>
      <h2>Invoice details</h2>
      <p class="muted">Send the exact Monero amount below to the local wallet subaddress.</p>
    </div>
    <strong>{invoice["amount_xmr"]} XMR</strong>
  </div>
  <div class="stack">
    <div>
      <p class="eyebrow">Send to this address</p>
      <p><code>{invoice["address"]}</code></p>
    </div>
    <div>
      <p class="eyebrow">Delivery path</p>
      <p><code>{invoice["delivery_path"]}</code></p>
    </div>
    <div>
      <p class="eyebrow">Status</p>
      <p>{status_title}</p>
    </div>
  </div>
</section>

<section class="stack" style="margin-top:16px;">
  <article class="card">
    <h2>1. Pay the invoice</h2>
    <p>Send the exact amount above from your Monero wallet.</p>
  </article>
  <article class="card">
    <h2>2. Confirmations</h2>
    <p class="muted">Required confirmations: {invoice["confirmations_required"]}. The watcher tracks invoice_created → payment_seen → paid → delivered.</p>
  </article>
  <article class="card">
    <h2>3. Delivery</h2>
    {delivery_block}
  </article>
</section>
'''


def write_order_artifacts(cur, order, invoice):
    item = CATALOG[order['sku']]
    out_dir = BASE / 'orders' / str(order['id'])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'invoice.json').write_text(json.dumps(invoice, indent=2) + '\n', encoding='utf-8')
    (out_dir / 'index.md').write_text(render_order_page(order, item, invoice), encoding='utf-8')
    cur.execute('UPDATE orders SET updated_at=datetime("now") WHERE id=?', (order['id'],))


def log_line(message):
    LOG_PATH.open('a', encoding='utf-8').write(message + '\n')


def matched_order(cur, amount):
    cur.execute(
        'SELECT id, sku, status, amount_xmr, delivery_path, delivery_url, wallet_address, confirmations_required, customer_ref, payment_txid FROM orders WHERE stream_name=? AND status IN ("invoice_created", "payment_seen", "paid") AND ABS(COALESCE(amount_xmr, 0) - ?) < 0.0000001 ORDER BY id DESC LIMIT 1',
        (CONFIG['stream_name'], amount),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'sku': row[1],
        'status': row[2],
        'amount_xmr': row[3],
        'delivery_path': row[4],
        'delivery_url': row[5],
        'wallet_address': row[6],
        'confirmations_required': row[7],
        'customer_ref': row[8],
        'payment_txid': row[9],
    }


def load_invoice(order_id):
    path = BASE / 'orders' / str(order_id) / 'invoice.json'
    return json.loads(path.read_text(encoding='utf-8'))


def save_order_state(cur, order_id, status, txid=None, confirmed_at=None, delivered_at=None):
    now = datetime.now(timezone.utc).isoformat()
    sets = ['status=?', 'updated_at=datetime("now")']
    values = [status]
    if txid is not None:
        sets.append('payment_txid=?')
        values.append(txid)
    if confirmed_at is not None:
        sets.append('confirmed_at=?')
        values.append(confirmed_at)
    if delivered_at is not None:
        sets.append('delivered_at=?')
        values.append(delivered_at)
    values.append(order_id)
    cur.execute(f'UPDATE orders SET {", ".join(sets)} WHERE id=?', values)
    return now


def fetch_order(cur, order_id):
    cur.execute('SELECT id, sku, status, amount_xmr, delivery_path, delivery_url, wallet_address, confirmations_required, customer_ref, payment_txid FROM orders WHERE id=?', (order_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        'id': row[0],
        'sku': row[1],
        'status': row[2],
        'amount_xmr': row[3],
        'delivery_path': row[4],
        'delivery_url': row[5],
        'wallet_address': row[6],
        'confirmations_required': row[7],
        'customer_ref': row[8],
        'payment_txid': row[9],
    }


def log_payment_event(cur, tx, amount, txid):
    cur.execute('SELECT 1 FROM payment_events WHERE txid=?', (txid,))
    if cur.fetchone():
        return False
    cur.execute(
        'INSERT INTO payment_events(stream_name, txid, amount_xmr, height, payload) VALUES(?,?,?,?,?)',
        (CONFIG['stream_name'], txid, amount, tx.get('height'), json.dumps(tx)),
    )
    cur.execute(
        'INSERT INTO earnings(stream_name, event_date, amount, currency, note) VALUES(?,?,?,?,?)',
        (CONFIG['stream_name'], datetime.now(timezone.utc).date().isoformat(), amount, 'XMR', f'Payment detected {txid}'),
    )
    return True


def release_delivery(cur, order, txid, amount):
    invoice = load_invoice(order['id'])
    confirmed_at = datetime.now(timezone.utc).isoformat()
    save_order_state(cur, order['id'], 'paid', txid=txid, confirmed_at=confirmed_at)
    order = fetch_order(cur, order['id'])
    invoice.update(
        {
            'status': 'paid',
            'payment_txid': txid,
            'confirmed_at': confirmed_at,
            'updated_at': confirmed_at,
            'amount_xmr': format(amount, 'f'),
        }
    )
    write_order_artifacts(cur, order, invoice)
    delivered_at = datetime.now(timezone.utc).isoformat()
    save_order_state(cur, order['id'], 'delivered', txid=txid, confirmed_at=confirmed_at, delivered_at=delivered_at)
    order = fetch_order(cur, order['id'])
    invoice.update({'status': 'delivered', 'delivered_at': delivered_at, 'updated_at': delivered_at})
    write_order_artifacts(cur, order, invoice)


def main():
    transfers = rpc('get_transfers', {'in': True, 'pool': True})
    balance = rpc('get_balance')
    incoming = []
    result = transfers.get('result', {})
    incoming.extend(result.get('in', []) or [])
    incoming.extend(result.get('pool', []) or [])

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ensure_schema(cur)
    detected = 0
    released = 0

    for tx in incoming:
        txid = tx.get('txid') or tx.get('tx_hash')
        if not txid:
            continue
        amount_atomic = tx.get('amount', 0) or 0
        amount = float(amount_atomic) / 1e12 if amount_atomic else 0.0
        confirmations = int(tx.get('confirmations') or 0)
        matched = matched_order(cur, amount)
        if not matched:
            log_payment_event(cur, tx, amount, txid)
            continue

        log_payment_event(cur, tx, amount, txid)
        detected += 1
        if confirmations >= int(matched['confirmations_required'] or CONFIG.get('confirmations', 10)):
            release_delivery(cur, matched, txid, amount)
            released += 1
        else:
            save_order_state(cur, matched['id'], 'payment_seen', txid=txid)
            order = fetch_order(cur, matched['id'])
            invoice = load_invoice(matched['id'])
            invoice.update(
                {
                    'status': 'payment_seen',
                    'payment_txid': txid,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
            )
            write_order_artifacts(cur, order, invoice)

    conn.commit()
    conn.close()
    message = (
        f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] payment_watch: "
        f"balance={balance.get('result', {}).get('balance')} detected={detected} released={released}"
    )
    log_line(message)
    print(message)


if __name__ == '__main__':
    main()
