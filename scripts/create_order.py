from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import argparse
import json
import sqlite3
import urllib.request

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
DB_PATH = ROOT / 'db' / 'earnings.sqlite3'
CONFIG = json.loads((BASE / 'config' / 'payment.json').read_text(encoding='utf-8'))
if not CONFIG.get('enabled', True):
    raise SystemExit(CONFIG.get('paused_reason', 'Storefront is paused.'))
CATALOG = json.loads((BASE / '_data' / 'catalog.json').read_text(encoding='utf-8'))

STATUS_COPY = {
    'invoice_created': ('Invoice created', 'Waiting for payment.'),
    'payment_seen': ('Payment seen', 'The wallet saw the transfer; waiting for confirmations.'),
    'paid': ('Paid', 'Required confirmations reached.'),
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
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def ensure_schema(cur):
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
        'delivery_path': "TEXT",
        'delivery_url': "TEXT",
        'wallet_address': "TEXT",
        'address_index': "INTEGER",
        'confirmations_required': "INTEGER NOT NULL DEFAULT 10",
        'confirmed_at': "TEXT",
        'delivered_at': "TEXT",
    }
    for column, definition in columns.items():
        if column not in existing:
            cur.execute(f'ALTER TABLE orders ADD COLUMN {column} {definition}')


def find_item(sku):
    return next((item for item in CATALOG if item['sku'] == sku), None)


def unique_amount(order_id, base_price):
    price = Decimal(str(base_price))
    bump = Decimal(order_id) * Decimal('0.000001')
    return (price + bump).quantize(Decimal('0.000000000001'))


def order_status_line(status):
    title, note = STATUS_COPY.get(status, (status.replace('_', ' ').title(), ''))
    return title, note


def render_order_page(order, item, invoice, released=False):
    order_id = order['id']
    status_title, status_note = order_status_line(order['status'])
    delivery_url = invoice['delivery_url'] if released else None
    delivery_block = (
        f'<p><a class="btn" href="{delivery_url}">Download your file</a></p>'
        if delivery_url
        else '<p class="muted">Delivery link will appear here automatically after payment confirms.</p>'
    )
    status_badge = f'<span class="pill">{status_title}</span>'
    return f'''---
layout: default
title: Order #{order_id} — {item["name"]}
permalink: /orders/{order_id}/
---

<section class="hero">
  <p class="eyebrow">Order #{order_id}</p>
  <h1>Pay <span class="accent">{invoice["amount_xmr"]} XMR</span> to unlock delivery.</h1>
  <p class="lead">This invoice is tied to your order. After the local wallet RPC sees the payment and the required confirmations land, the order flips to paid and the download link appears on this page.</p>
</section>

<section class="card">
  <div class="meta">
    <span class="pill">{item["format"]}</span>
    <span class="pill">{item["delivery_method"]}</span>
    {status_badge}
  </div>
  <div class="order-card-head">
    <div>
      <h2>{item["name"]}</h2>
      <p class="muted">{status_note}</p>
    </div>
    <strong>{invoice["amount_xmr"]} XMR</strong>
  </div>
  <div class="stack">
    <div>
      <p class="eyebrow">Send to this address</p>
      <p><code>{invoice["address"]}</code></p>
    </div>
    <div>
      <p class="eyebrow">Exact invoice amount</p>
      <p><code>{invoice["amount_xmr"]} XMR</code></p>
    </div>
    <div>
      <p class="eyebrow">Delivery path</p>
      <p><code>{invoice["delivery_path"]}</code></p>
    </div>
  </div>
</section>

<section class="stack" style="margin-top:16px;">
  <article class="card">
    <h2>1. Pay the invoice</h2>
    <p>Send the exact amount above from your Monero wallet.</p>
  </article>
  <article class="card">
    <h2>2. Wait for confirmations</h2>
    <p class="muted">Required confirmations: {invoice["confirmations_required"]}. Status updates through invoice_created → payment_seen → paid.</p>
  </article>
  <article class="card">
    <h2>3. Delivery</h2>
    {delivery_block}
  </article>
</section>
'''


def write_order_artifacts(order, item, invoice, released=False):
    out_dir = BASE / 'orders' / str(order['id'])
    out_dir.mkdir(parents=True, exist_ok=True)
    invoice_path = out_dir / 'invoice.json'
    page_path = out_dir / 'index.md'
    invoice_path.write_text(json.dumps(invoice, indent=2) + '\n', encoding='utf-8')
    page_path.write_text(render_order_page(order, item, invoice, released=released), encoding='utf-8')


def main():
    ap = ArgumentParser(description='Create a local Monero invoice and order page.')
    ap.add_argument('--sku', required=True)
    ap.add_argument('--email', required=True)
    args = ap.parse_args()

    item = find_item(args.sku)
    if not item:
        raise SystemExit(f'Unknown sku: {args.sku}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ensure_schema(cur)
    cur.execute(
        'INSERT INTO orders(stream_name, sku, customer_ref, amount_xmr, amount_usd, status, delivery_path, confirmations_required) VALUES(?,?,?,?,?,?,?,?)',
        ('Data Products', args.sku, args.email, float(item['price_xmr']), None, 'invoice_created', item.get('delivery_path'), int(CONFIG.get('confirmations', 10))),
    )
    order_id = cur.lastrowid

    amount = unique_amount(order_id, item['price_xmr'])
    wallet_address = CONFIG['wallet_address']
    address_index = None
    try:
        created = rpc('create_address', {'account_index': 0, 'label': f'order-{order_id}'})
        result = created.get('result', {})
        wallet_address = result.get('address', wallet_address)
        address_index = result.get('address_index')
    except Exception:
        pass

    now = datetime.now(timezone.utc).isoformat()
    invoice = {
        'order_id': order_id,
        'sku': args.sku,
        'name': item['name'],
        'email': args.email,
        'amount_xmr': format(amount, 'f'),
        'address': wallet_address,
        'address_index': address_index,
        'delivery_path': item.get('delivery_path'),
        'delivery_url': item.get('delivery_path'),
        'confirmations_required': int(CONFIG.get('confirmations', 10)),
        'status': 'invoice_created',
        'order_url': f'/orders/{order_id}/',
        'created_at': now,
        'updated_at': now,
    }

    cur.execute(
        'UPDATE orders SET amount_xmr=?, wallet_address=?, address_index=?, delivery_url=?, updated_at=datetime("now") WHERE id=?',
        (float(amount), wallet_address, address_index, item.get('delivery_path'), order_id),
    )
    conn.commit()
    conn.close()

    order_record = {
        'id': order_id,
        'status': 'invoice_created',
    }
    write_order_artifacts(order_record, item, invoice, released=False)
    print(json.dumps(invoice, indent=2))


if __name__ == '__main__':
    main()
