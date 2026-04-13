---
layout: default
title: Alkaline Data
---

<p class="eyebrow">Digital products</p>
<h1>Alkaline Data</h1>
<p class="muted">A small catalog of useful downloads with privacy-friendly Monero checkout and simple delivery.</p>

<section class="grid">
  {% for item in site.data.catalog %}
  <article class="product">
    <div class="meta"><span class="pill">{{ item.format }}</span><span class="pill">{{ item.delivery_method }}</span></div>
    <h2>{{ item.name }}</h2>
    <p>{{ item.description }}</p>
    <p class="muted">{{ item.sample }}</p>
    <p><strong>{{ item.price_xmr }} XMR</strong></p>
    <a class="btn" href="{{ '/checkout/' | relative_url }}#{{ item.sku }}">Buy / request invoice</a>
  </article>
  {% endfor %}
</section>

<section class="card" style="margin-top:24px;">
  <h2>How checkout works</h2>
  <ol>
    <li>Pick a product.</li>
    <li>Create an invoice with the local order script.</li>
    <li>Pay the unique XMR amount.</li>
    <li>The watcher confirms payment and marks the order ready for delivery.</li>
  </ol>
</section>
