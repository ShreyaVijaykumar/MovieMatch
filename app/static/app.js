"use strict";

const $ = (s) => document.querySelector(s);
const check = async (r) => {
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};
const get = (u) => fetch(u).then(check);
const post = (u, b) =>
  fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(check);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const TMDB_CREDIT = "This product uses the TMDB API but is not endorsed or certified by TMDB.";
const KEY = "moviematch.ratings";
const NEED = 5;
const PAGE = 24;
const ROW = 20;
const GENRE_ROWS = 5;

const loadRatings = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
};
const saveRatings = () => {
  try {
    localStorage.setItem(KEY, JSON.stringify(ratings));
  } catch {}
};

let ratings = loadRatings();
const st = { tab: "home", genre: null, sort: "popular", q: "", offset: 0, fyGenre: null, seqMovies: 0, seqRecs: 0, seqPicks: 0, genres: [], posters: false };
let recTimer = null;

const count = () => Object.keys(ratings).length;
const hash = (n) => Math.abs(Math.imul(n | 0, 2654435761)) >>> 0;
const initials = (t) => t.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/* Rating stars */

function starsHtml(id) {
  return `<div class="stars" data-id="${id}" role="group" aria-label="Your rating">${[1, 2, 3, 4, 5]
    .map((n) => `<button data-n="${n}" aria-label="${n} stars">★</button>`)
    .join("")}</div>`;
}

function paint(id) {
  const r = ratings[id] || 0;
  document.querySelectorAll(`.stars[data-id="${id}"]`).forEach((el) =>
    el.querySelectorAll("button").forEach((b, i) => b.classList.toggle("on", i < r))
  );
  document.querySelectorAll(`.rate[data-id="${id}"]`).forEach((el) => (el.textContent = r ? `You: ${r}★` : ""));
}

document.addEventListener("click", (e) => {
  const b = e.target.closest(".stars button");
  if (!b) return;
  const id = b.parentElement.dataset.id;
  const n = +b.dataset.n;
  if (ratings[id] === n) delete ratings[id];
  else ratings[id] = n;
  saveRatings();
  paint(id);
  updateBadge();
  if (st.tab === "foryou") scheduleRecs(count() < NEED ? 0 : 900);
  if (st.tab === "home") homeRated();
});

function homeRated() {
  const n = count();
  if (n < NEED && st.picksMode === "start") {
    const note = $("#row-picks h2 small");
    if (note) note.textContent = `Rate ${NEED} movies you know to unlock picks (${n}/${NEED})`;
    return;
  }
  scheduleRecs(n < NEED ? 0 : 900);
}

/* Poster images (TMDB, optional) */

const img = (id, cls) => (st.posters ? `<img class="${cls}" src="/api/poster/${id}" alt="" loading="lazy" decoding="async">` : "");

function watchImg(im, host) {
  if (!im) return;
  const ok = () => host.classList.add("has-img");
  if (im.complete && im.naturalWidth) ok();
  im.onload = ok;
  im.onerror = () => im.remove();
}

/* Poster card */

function poster(m, extra = {}) {
  const h = hash(m.id);
  const el = document.createElement("article");
  el.className = "poster";
  el.innerHTML =
    `<div class="art" style="background:radial-gradient(circle at ${20 + (h % 60)}% ${15 + ((h >> 3) % 40)}%,rgba(248,204,34,${0.14 + (h % 7) / 50}),transparent 62%),` +
    `linear-gradient(${120 + (h % 90)}deg,#4a4b5b,#2b2c37 55%,#1b1c24)">` +
    `<span class="ini">${esc(initials(m.title))}</span><span class="yr">${m.year ?? ""}</span>${img(m.id, "pimg")}</div>` +
    (extra.match != null ? `<span class="pmatch">${extra.match}% match</span>` : "") +
    `<div class="cap"><h3>${esc(m.title)}</h3></div>` +
    `<div class="over"><h3>${esc(m.title)}</h3>` +
    `<div class="sub">${esc(m.genres.slice(0, 2).join(" · ") || "No genre")} · ★ ${m.avg.toFixed(1)} (${m.count})</div>` +
    (extra.because && extra.because.length ? `<div class="why">Because you liked ${esc(extra.because.join(" and "))}</div>` : "") +
    `${starsHtml(m.id)}<div class="rate" data-id="${m.id}"></div></div>`;
  watchImg(el.querySelector(".pimg"), el);
  el.querySelector(".art").onclick = () => openDetail(m.id);
  el.querySelector(".cap").onclick = () => openDetail(m.id);
  paint(m.id);
  return el;
}

function updateBadge() {
  const n = count();
  $("#badge").hidden = n === 0;
  $("#badge").textContent = n;
  $("#clear").hidden = n === 0;
  $("#fy-genres").hidden = n < NEED;
  $("#fy-progress").textContent = `${Math.min(n, NEED)} of ${NEED} rated`;
}

function chips(el, genres, current, onPick) {
  el.innerHTML = ["All", ...genres]
    .map((g) => `<button class="chip${(g === "All" ? null : g) === current ? " on" : ""}" data-g="${esc(g)}">${esc(g)}</button>`)
    .join("");
  el.onclick = (e) => {
    const b = e.target.closest(".chip");
    if (b) onPick(b.dataset.g === "All" ? null : b.dataset.g);
  };
}

/* Rows */

function rowShell(id, title, note) {
  const sec = document.createElement("div");
  sec.className = "row";
  sec.id = id;
  sec.innerHTML =
    `<h2>${esc(title)}${note ? `<small>${esc(note)}</small>` : ""}</h2>` +
    `<div class="track-wrap"><button class="arrow l" aria-label="Scroll left" hidden>‹</button>` +
    `<div class="track">${'<div class="skel"></div>'.repeat(8)}</div>` +
    `<button class="arrow r" aria-label="Scroll right">›</button></div>`;
  const track = sec.querySelector(".track");
  const l = sec.querySelector(".arrow.l");
  const r = sec.querySelector(".arrow.r");
  const sync = () => {
    l.hidden = track.scrollLeft < 8;
    r.hidden = track.scrollLeft + track.clientWidth >= track.scrollWidth - 8;
  };
  l.onclick = () => track.scrollBy({ left: -track.clientWidth * 0.85, behavior: "smooth" });
  r.onclick = () => track.scrollBy({ left: track.clientWidth * 0.85, behavior: "smooth" });
  track.addEventListener("scroll", sync, { passive: true });
  sec.sync = sync;
  return sec;
}

function fillRow(sec, cards) {
  const track = sec.querySelector(".track");
  track.innerHTML = "";
  cards.forEach((c) => track.append(c));
  track.scrollLeft = 0;
  requestAnimationFrame(sec.sync);
}

async function picksContent() {
  if (count() < NEED) {
    const items = await get("/api/onboarding?n=24");
    return { title: "Start here", note: `Rate ${NEED} movies you know to unlock picks (${count()}/${NEED})`, cards: items.map((m) => poster(m)), top: null };
  }
  const r = await post("/api/recommend", { ratings, limit: ROW });
  return {
    title: "Top picks for you",
    note: `from ${r.n_ratings} ratings`,
    cards: r.items.map((m) => poster(m, { match: m.match, because: m.because })),
    top: r.items[0] || null,
  };
}

async function renderPicks() {
  const seq = ++st.seqPicks;
  const c = await picksContent();
  if (seq !== st.seqPicks) return;
  st.picksMode = c.top || count() >= NEED ? "recs" : "start";
  const old = $("#row-picks");
  const sec = rowShell("row-picks", c.title, c.note);
  if (old) old.replaceWith(sec);
  else $("#rows").prepend(sec);
  fillRow(sec, c.cards);
  if (c.top) renderHero(c.top, `Top pick for you · ${c.top.match}% match`);
  else if (st.heroDefault) renderHero(st.heroDefault, "Top rated");
}

function renderHero(m, eyebrow) {
  $("#hero").innerHTML =
    `<span class="ghost">${esc(initials(m.title))}</span>${img(m.id, "hero-poster")}<div class="hero-in"><div class="eyebrow">${esc(eyebrow)}</div>` +
    `<h1>${esc(m.title)}</h1><div class="facts"><span>${m.year ?? ""}</span><span class="hi">★ ${m.avg.toFixed(1)}</span>` +
    `<span>${m.count.toLocaleString()} ratings</span><span>${esc(m.genres.slice(0, 3).join(" · "))}</span></div>` +
    `<div class="cta"><button class="btn primary" id="hero-open">★ Rate &amp; see similar</button><button class="btn" id="hero-browse">Browse all</button></div></div>`;
  watchImg($("#hero .hero-poster"), $("#hero"));
  $("#hero-open").onclick = () => openDetail(m.id);
  $("#hero-browse").onclick = () => showTab("browse");
}

async function renderHome() {
  const rows = $("#rows");
  rows.innerHTML = "";
  const specs = [
    { id: "row-popular", title: "Most rated", q: "sort=popular" },
    { id: "row-top", title: "Top rated", q: "sort=rating" },
    ...st.genres.slice(0, GENRE_ROWS).map((g) => ({ id: `row-g-${g}`, title: `Top ${g}`, q: `sort=rating&genre=${encodeURIComponent(g)}` })),
  ];
  const shells = specs.map((s) => rowShell(s.id, s.title));
  shells.forEach((s) => rows.append(s));
  const results = await Promise.all(specs.map((s) => get(`/api/movies?${s.q}&limit=${ROW}`)));
  results.forEach((r, i) => fillRow(shells[i], r.items.map((m) => poster(m))));
  st.heroDefault = results[1].items[0] || results[0].items[0];
  await renderPicks();
}

/* Browse */

async function loadMovies(reset) {
  const seq = ++st.seqMovies;
  if (reset) st.offset = 0;
  const p = new URLSearchParams({ q: st.q, sort: st.sort, limit: PAGE, offset: st.offset });
  if (st.genre) p.set("genre", st.genre);
  const r = await get(`/api/movies?${p}`);
  if (seq !== st.seqMovies) return;
  if (reset) $("#grid").innerHTML = "";
  r.items.forEach((m) => $("#grid").append(poster(m)));
  st.offset += r.items.length;
  $("#more").hidden = st.offset >= r.total;
  $("#empty").hidden = r.total > 0;
}

/* For you */

function scheduleRecs(delay = 0) {
  clearTimeout(recTimer);
  recTimer = setTimeout(() => (st.tab === "home" ? renderPicks() : renderForYou()), delay);
}

async function renderForYou() {
  updateBadge();
  const n = count();
  $("#fy-start").hidden = n >= NEED;
  if (n < NEED) {
    $("#fy-list").innerHTML = "";
    $("#fy-empty").hidden = true;
    if (!$("#onboard").children.length) {
      const items = await get("/api/onboarding?n=24");
      items.forEach((m) => $("#onboard").append(poster(m)));
    }
    return;
  }
  const seq = ++st.seqRecs;
  const r = await post("/api/recommend", { ratings, limit: PAGE, genre: st.fyGenre });
  if (seq !== st.seqRecs) return;
  $("#fy-list").innerHTML = "";
  r.items.forEach((m) => $("#fy-list").append(poster(m, { match: m.match, because: m.because })));
  $("#fy-empty").hidden = r.items.length > 0;
}

/* Detail */

async function openDetail(id) {
  const d = await get(`/api/movies/${id}`);
  const dlg = $("#detail");
  dlg.innerHTML =
    `<div class="dtop"><button class="x" aria-label="Close">✕</button>${img(d.id, "dposter")}<h2>${esc(d.title)}</h2>` +
    `<div class="facts"><span>${d.year ?? ""}</span><span class="hi">★ ${d.avg.toFixed(1)}</span><span>${d.count.toLocaleString()} ratings</span>` +
    `<span>${esc(d.genres.join(" · ") || "No genre")}</span></div>` +
    `<div class="muted">Your rating</div>${starsHtml(d.id)}</div>` +
    `<div class="dbody"><h3>More like this</h3><div class="sim">${d.similar
      .map((s) => `<button class="simcard" data-id="${s.id}">${esc(s.title)}<span>${s.year ?? ""} · ${esc(s.genres.slice(0, 2).join(" · "))}</span></button>`)
      .join("")}</div></div>`;
  paint(d.id);
  watchImg(dlg.querySelector(".dposter"), dlg.querySelector(".dtop"));
  dlg.querySelector(".x").onclick = () => dlg.close();
  dlg.querySelectorAll(".simcard").forEach((b) => (b.onclick = () => openDetail(+b.dataset.id)));
  if (!dlg.open) dlg.showModal();
}

$("#detail").addEventListener("click", (e) => {
  if (e.target === $("#detail")) $("#detail").close();
});

/* About */

function metricsHtml(m) {
  if (!m.rmse) return '<p class="muted">Offline metrics not computed. Run: python -m app.evaluate</p>';
  const rm = Object.entries(m.rmse);
  const bestRmse = Math.min(...rm.map(([, v]) => v));
  const methods = Object.keys(m.ranking);
  const keys = Object.keys(m.ranking[methods[0]]);
  const bestRank = keys.map((k) => Math.max(...methods.map((x) => m.ranking[x][k])));
  return (
    `<h3>Offline evaluation</h3><p class="muted">Train on the first 80% of each user's ratings, test on the last 20%. ` +
    `${m.users_evaluated} users, ${m.test_ratings.toLocaleString()} test ratings.</p>` +
    `<table><thead><tr><th>Rating error (RMSE, lower is better)</th><th>RMSE</th></tr></thead><tbody>${rm
      .map(([k, v]) => `<tr><td>${esc(k)}</td><td${v === bestRmse ? ' class="best"' : ""}>${v}</td></tr>`)
      .join("")}</tbody></table>` +
    `<table><thead><tr><th>Top-10 ranking (higher is better)</th>${keys.map((k) => `<th>${esc(k)}</th>`).join("")}</tr></thead><tbody>${methods
      .map((x) => `<tr><td>${esc(x)}</td>${keys.map((k, i) => `<td${m.ranking[x][k] === bestRank[i] ? ' class="best"' : ""}>${m.ranking[x][k]}</td>`).join("")}</tr>`)
      .join("")}</tbody></table>`
  );
}

async function renderAbout() {
  const [meta, metrics] = await Promise.all([get("/api/meta"), get("/api/metrics")]);
  $("#about").innerHTML =
    `<div class="about"><h2 class="title">About</h2><div class="stats"><div><b>${meta.movies.toLocaleString()}</b><span>movies</span></div>` +
    `<div><b>${meta.ratings.toLocaleString()}</b><span>ratings</span></div><div><b>${meta.users.toLocaleString()}</b><span>users</span></div></div>` +
    `<div><h3>How it works</h3><ul><li>Rate movies. Ratings stay in your browser.</li>` +
    `<li>A matrix factorisation model learns movie factors from all users' ratings.</li>` +
    `<li>Your ratings are folded into those factors to score unseen movies.</li></ul></div>` +
    `<div>${metricsHtml(metrics)}</div>` +
    `<p class="muted">Data: F. Maxwell Harper and Joseph A. Konstan. 2015. The MovieLens Datasets: History and Context. ACM TiiS 5(4).</p>` +
    (st.posters ? `<p class="muted">${TMDB_CREDIT}</p>` : "") + `</div>`;
}

/* Tabs and init */

function showTab(tab) {
  st.tab = tab;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  document.querySelectorAll("main > section").forEach((s) => (s.hidden = s.id !== tab));
  window.scrollTo({ top: 0 });
  if (tab === "browse" && !$("#grid").children.length) loadMovies(true);
  if (tab === "foryou") renderForYou();
  if (tab === "about") renderAbout();
  if (tab === "home") renderPicks();
}

async function init() {
  const meta = await get("/api/meta");
  st.genres = meta.genres;
  st.posters = meta.posters;
  if (st.posters) $("footer").textContent += ` · ${TMDB_CREDIT}`;

  const pickBrowse = (g) => {
    st.genre = g;
    chips($("#genres"), st.genres, g, pickBrowse);
    loadMovies(true);
  };
  chips($("#genres"), st.genres, null, pickBrowse);
  const pickFy = (g) => {
    st.fyGenre = g;
    chips($("#fy-genres"), st.genres, g, pickFy);
    renderForYou();
  };
  chips($("#fy-genres"), st.genres, null, pickFy);

  $("#sort").onchange = (e) => {
    st.sort = e.target.value;
    loadMovies(true);
  };
  $("#more").onclick = () => loadMovies(false);
  let t;
  $("#q").oninput = (e) => {
    clearTimeout(t);
    t = setTimeout(() => {
      st.q = e.target.value.trim();
      if (st.tab !== "browse") showTab("browse");
      loadMovies(true);
    }, 250);
  };
  $("#clear").onclick = () => {
    ratings = {};
    saveRatings();
    document.querySelectorAll(".stars").forEach((el) => paint(el.dataset.id));
    renderForYou();
  };
  document.querySelectorAll("#tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));
  const onScroll = () => $("#nav").classList.toggle("solid", window.scrollY > 24);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  updateBadge();
  await renderHome();
}

init().catch((e) => document.body.insertAdjacentHTML("beforeend", `<pre style="padding:20px;color:#F8CC22">${esc(e.message)}</pre>`));
