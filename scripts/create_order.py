from __future__ import annotations

from pathlib import Path
import argparse
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
DB_PATH = ROOT / 'db' / 'earnings.sqlite3'
CONFIG = json.loads((BASE / 'config' / 'payment.json').read_text(encoding='utf-8'))
CATALOG = json.loads((BASE / '_data' / 'catalog.json').read_text(encoding='utf-8'))


def rpc(method, params=None):
    payload = {'jsonrpc': '2.0', 'id': '0', 'method': method}
    if params is not None:
        payload['params'] = params
    req = urllib.request.Request(CONFIG['rpc_url'], data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sku', required=True)
    ap.add_argument('--email', required=True)
    args = ap.parse_args()
    item = next((x for x in CATALOG if x['sku'] == args.sku), None)
    if not item:
        raise SystemExit(f'Unknown sku: {args.sku}')
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
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
        )
    """)
    cur.execute('INSERT INTO orders(stream_name, sku, customer_ref, amount_xmr, amount_usd, status) VALUES(?,?,?,?,?,?)', ('Data Products', args.sku, args.email, item['price_xmr'], None, 'invoice_created'))
    order_id = cur.lastrowid
    invoice_amount = float(item['price_xmr']) + (order_id % 97) * 0.000001
    try:
        sub = rpc('create_address', {'account_index': 0, 'label': f'order-{order_id}'})
        address = sub['result'].get('address')
    except Exception:
        address = CONFIG['wallet_address']
    invoice = {
        'order_id': order_id,
        'sku': args.sku,
        'name': item['name'],
        'email': args.email,
        'amount_xmr': round(invoice_amount, 12),
        'address': address,
        'status': 'invoice_created',
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    out_dir = BASE / 'orders' / str(order_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'invoice.json').write_text(json.dumps(invoice, indent=2) + '\n', encoding='utf-8')
    (out_dir / 'index.md').write_text(f'''---\nlayout: default\ntitle: Invoice {order_id}\npermalink: /orders/{order_id}/\n---\n\n<h1>Invoice {order_id}</h1>\n<p><strong>{item['name']}</strong></p>\n<p>Send exactly <strong>{invoice['amount_xmr']} XMR</strong> to:</p>\n<p><code>{address}</code></p>\n<p class="muted">After payment confirms, the watcher will mark the order paid and release delivery.</p>\n''', encoding='utf-8')
    conn.commit(); conn.close()
    print(json.dumps(invoice, indent=2))


if __name__ == '__main__':
    main()
