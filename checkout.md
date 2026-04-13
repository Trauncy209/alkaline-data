---
layout: default
title: Checkout
permalink: /checkout/
---

<section class="hero">
  <p class="eyebrow">Checkout paused</p>
  <h1>Buying is on hold while the offer is simplified.</h1>
  <p class="lead">The order code remains in place, but checkout is paused so we can avoid sending buyers into a confusing or premature purchase flow.</p>
</section>

<section class="card">
  <h2>Order state flow</h2>
  <div class="state-flow">
    <span class="state">invoice_created</span>
    <span class="state">payment_seen</span>
    <span class="state">paid</span>
    <span class="state">delivered</span>
  </div>
  <p class="muted">The store uses the local wallet RPC already wired into <code>scripts/create_order.py</code> and <code>scripts/payment_watch.py</code>. No external processor is involved.</p>
</section>

<section class="stack">
  {% for item in site.data.catalog %}
  <article class="card order-card" id="{{ item.sku }}">
    <div class="order-card-head">
      <div>
        <p class="eyebrow">{{ item.format }}</p>
        <h2>{{ item.name }}</h2>
      </div>
      <strong>{{ item.price_xmr }} XMR</strong>
    </div>
    <p>{{ item.description }}</p>
    <ul class="clean">
      <li><strong>Product page:</strong> <a href="{{ '/products/' | append: item.sku | append: '/' | relative_url }}">Open page</a></li>
      <li><strong>Delivery:</strong> {{ item.delivery_method }} via {{ item.delivery_path }}</li>
      <li><strong>Invoice command:</strong> <code>python3 scripts/create_order.py --sku {{ item.sku }} --email buyer@example.com</code></li>
    </ul>
  </article>
  {% endfor %}
</section>

<section class="card" style="margin-top:18px;">
  <h2>What the buyer sees after payment confirms</h2>
  <ul class="clean">
    <li>The order page changes from a pay-now invoice to a paid status.</li>
    <li>The delivery link appears automatically on the same page.</li>
    <li>The link points directly to the downloadable asset for that product.</li>
  </ul>
</section>
