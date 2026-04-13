---
layout: default
title: Checkout
permalink: /checkout/
---

<p class="eyebrow">Checkout</p>
<h1>Request an invoice</h1>
<p class="muted">Use the order script to generate a unique XMR invoice and local order page.</p>

<section class="stack">
  {% for item in site.data.catalog %}
  <div class="card" id="{{ item.sku }}">
    <h2>{{ item.name }}</h2>
    <p>{{ item.description }}</p>
    <p><strong>{{ item.price_xmr }} XMR</strong></p>
    <p class="muted">Run: <code>python3 scripts/create_order.py --sku {{ item.sku }} --email buyer@example.com</code></p>
  </div>
  {% endfor %}
</section>
