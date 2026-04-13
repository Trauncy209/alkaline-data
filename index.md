---
layout: default
title: Alkaline Data
---

<section class="hero">
  <p class="eyebrow">Store paused</p>
  <h1>We are simplifying the offer before we sell again.</h1>
  <p class="lead">The storefront and payment flow are temporarily paused while the products, wording, and delivery experience are tightened up. The wallet and order code still exist, but the front end is no longer pushing buyers into a confusing flow.</p>
</section>

<section class="steps card">
  <div>
    <p class="eyebrow">How it works</p>
    <h2>One obvious path from product page to delivery</h2>
  </div>
  <ol class="timeline">
    <li><strong>1. View product</strong><span>Read the page, choose the item, and open the invoice form.</span></li>
    <li><strong>2. Pay XMR</strong><span>Create a local order, send the exact invoice amount, and wait for confirmations.</span></li>
    <li><strong>3. Auto-delivery unlocks</strong><span>The watcher marks the order paid and reveals the download link on the order page.</span></li>
  </ol>
</section>

<section id="catalog" class="stack">
  <div>
    <p class="eyebrow">Catalog</p>
    <h2>Available downloads</h2>
  </div>
  <div class="grid">
    {% for item in site.data.catalog %}
    <article class="product">
      <div class="meta">
        <span class="pill">{{ item.format }}</span>
        <span class="pill">{{ item.delivery_method }}</span>
      </div>
      <h3>{{ item.name }}</h3>
      <p>{{ item.description }}</p>
      <p class="muted">{{ item.sample }}</p>
      <div class="price-row">
        <strong>{{ item.price_xmr }} XMR</strong>
        <span class="muted">Exact invoice amount is generated per order.</span>
      </div>
      <div class="card-actions">
        <a class="btn" href="{{ '/products/' | append: item.sku | append: '/' | relative_url }}">View product</a>
        <a class="btn btn-secondary" href="{{ '/checkout/' | relative_url }}#{{ item.sku }}">Buy now</a>
      </div>
    </article>
    {% endfor %}
  </div>
</section>
