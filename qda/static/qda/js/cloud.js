/*
 * Sync with the signed-in researcher's account on the SST server.
 *
 * The browser copy stays the working copy — every page still reads and
 * writes it synchronously (app.js) — and this module pulls the account's
 * latest copies when a page opens and uploads each change shortly after it
 * is made, through the JSON API in qda/api.py.
 *
 * Every upload says which revision of the project it was based on. If the
 * project changed in the account since (on another computer), the server
 * answers 409 with its copy and nothing is overwritten: an untouched copy
 * here is replaced, otherwise this browser's edits are kept as a separate
 * "conflicted copy". Deletions are tombstones, so they reach the user's
 * other computers.
 *
 * Signing in and out happens on server pages (the tool's sign-in page and
 * the SST site's account pages); this module learns who is signed in from
 * window.TB_CONFIG.user, which the page sets.
 */
(function () {
  "use strict";

  var META_KEY = "tb_sync_meta";      // per project: { remoteRev, dirty, rev, localOnly, sourcesHash }
  var OWNER_KEY = "tb_sync_owner";    // whose synced copies this browser holds
  var WRITER_KEY = "tb_sync_writer";  // this browser's id: lets the server accept a resent upload
  var PUSH_DELAY = 700;
  var NETWORK_TIMEOUT = 15000;        // plus extra time for big uploads, see request()
  var DOWNLOAD_TIMEOUT = 300000;      // whole projects with transcripts, on slow connections
  var READY_WAIT = 15000;             // pages draw after this even if a download is still going
  var RETRY_DELAY = 30000;
  var GZIP_ABOVE = 20000;             // characters

  var TB = window.TB;
  var cfg = window.TB_CONFIG || {};
  var urls = cfg.urls || {};
  var PROJECTS_API = cfg.projectsApi || "";
  var enabled = !!PROJECTS_API;
  var user = enabled ? (cfg.user || null) : null;
  var state = !enabled ? "local" : user ? "connecting" : "signed-out";
  var lastError = "";
  var lastSyncedAt = 0;
  var handlers = {};
  var timers = {};
  var inflight = {};
  var again = {};
  var retryTimer = null;
  var booted = false;

  // ------------------------------------------------------------ helpers
  // One-off notices raised before the page has subscribed (sync starts
  // before DOMContentLoaded) are held and delivered on subscription.
  var HELD = { importNeeded: true, conflict: true, restored: true, remoteChange: true, sessionExpired: true };
  var held = {};
  function call(fn, payload) {
    try { fn(payload); } catch (e) { console.error(e); }
  }
  function on(name, fn) {
    (handlers[name] = handlers[name] || []).push(fn);
    (held[name] || []).splice(0).forEach(function (p) { call(fn, p); });
  }
  function emit(name, payload) {
    var list = handlers[name] || [];
    if (!list.length && HELD[name]) { (held[name] = held[name] || []).push(payload); return; }
    list.forEach(function (fn) { call(fn, payload); });
  }
  var notice = emit;

  function readMeta() {
    try { return JSON.parse(localStorage.getItem(META_KEY) || "{}"); } catch (e) { return {}; }
  }
  function writeMeta(m) { localStorage.setItem(META_KEY, JSON.stringify(m)); }
  function getMeta(id) { return readMeta()[id] || null; }
  function patchMeta(id, patch) {
    var m = readMeta();
    m[id] = Object.assign(m[id] || {}, patch);
    writeMeta(m);
  }
  function dropMeta(id) {
    var m = readMeta();
    delete m[id];
    writeMeta(m);
  }

  function writerId() {
    var id = localStorage.getItem(WRITER_KEY);
    if (!id) {
      id = "w" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(WRITER_KEY, id);
    }
    return id;
  }

  function isUntouchedDemo(project) {
    return !!(project && project.id === TB.DEMO_PROJECT_ID && TB.isUntouchedDemo && TB.isUntouchedDemo(project));
  }

  // Transcripts (project.sources) are only uploaded when their content
  // changed, so coding a passage sends the small part of the project
  // rather than every transcript again.
  function hashText(s) {
    var h = 0x811c9dc5;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    return (h >>> 0).toString(36) + ":" + s.length;
  }
  function sourcesHash(sources) { return hashText(JSON.stringify(sources || [])); }
  function usableRow(row) {
    return !!(row && row.project && typeof row.project === "object" &&
      Array.isArray(row.project.themes) && Array.isArray(row.project.codings));
  }
  // Writes an account copy into the browser; returns its transcripts' hash.
  function writeFromRow(row) {
    var project = Object.assign({}, row.project, { id: row.id, sources: Array.isArray(row.sources) ? row.sources : [] });
    TB.writeProjectLocal(project, row.updated || undefined);
    return sourcesHash(project.sources);
  }
  function bodyFor(project, m) {
    if (!project) return { body: { deleted: true }, hash: null };
    var data = Object.assign({}, project);
    delete data.sources;
    var body = { deleted: false, project: data };
    var hash = sourcesHash(project.sources);
    if (m.remoteRev == null || m.sourcesHash !== hash) body.sources = project.sources || [];
    return { body: body, hash: hash };
  }
  function withSources(id, body) {
    if (body.deleted || body.sources) return body;
    var p = TB.loadProject(id);
    return Object.assign({}, body, { sources: (p && p.sources) || [] });
  }

  // --------------------------------------------------------------- http
  function csrfToken() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : (cfg.csrfToken || "");
  }

  function httpError(status, data) {
    var e = new Error((data && data.message) || ("The server answered " + status + "."));
    e.status = status;
    e.data = data || {};
    return e;
  }

  // Large uploads are gzipped (transcripts shrink to about a quarter), which
  // matters on mobile data. Falls back to plain JSON where unsupported.
  function prepareBody(text) {
    var plain = { data: text, size: text.length, gzip: false };
    if (text.length < GZIP_ABOVE || typeof CompressionStream !== "function" || typeof Blob !== "function" || !Blob.prototype.stream) {
      return Promise.resolve(plain);
    }
    try {
      var stream = new Blob([text], { type: "application/json" }).stream().pipeThrough(new CompressionStream("gzip"));
      return new Response(stream).arrayBuffer().then(function (buf) {
        return { data: buf, size: buf.byteLength, gzip: true };
      }, function () { return plain; });
    } catch (e) {
      return Promise.resolve(plain);
    }
  }

  // Resolves { status, data } for any answer the callers handle themselves;
  // rejects on network failure, timeout, or a signed-out / switched session.
  function request(method, url, json, timeout) {
    return (json === undefined ? Promise.resolve(null) : prepareBody(JSON.stringify(json))).then(function (body) {
      var headers = { Accept: "application/json" };
      if (user) headers["X-TB-User"] = String(user.id);
      if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
      var ms = timeout || NETWORK_TIMEOUT;
      if (body) {
        headers["Content-Type"] = "application/json";
        if (body.gzip) headers["Content-Encoding"] = "gzip";
        ms += body.size / 4;   // allow for connections down to ~4 KB/s
      }
      var ctrl = typeof AbortController === "function" ? new AbortController() : null;
      var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, ms);
      return fetch(url, {
        method: method, headers: headers, body: body ? body.data : undefined,
        credentials: "same-origin", cache: "no-store", signal: ctrl ? ctrl.signal : undefined
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          clearTimeout(timer);
          if (res.status === 401) { sessionEnded(); throw httpError(401, data); }
          if (res.status === 409 && data && data.error === "user_changed") {
            window.location.reload();
            throw httpError(409, data);
          }
          if (res.status === 403) throw httpError(403, { message: "The server refused the request (security check). Reload the page." });
          return { status: res.status, data: data || {} };
        });
      }, function (err) {
        clearTimeout(timer);
        throw new Error(err && err.name === "AbortError" ? "timeout" : "network: " + ((err && err.message) || err));
      });
    });
  }

  function projectUrl(id) { return PROJECTS_API + encodeURIComponent(id) + "/"; }

  function expectOk(res) {
    if (res.status !== 200) throw httpError(res.status, res.data);
    return res.data;
  }

  // ------------------------------------------------------------- status
  function pendingCount() {
    var m = readMeta();
    return Object.keys(m).filter(function (id) { return m[id].dirty && !m[id].localOnly; }).length;
  }
  function status() {
    return {
      enabled: enabled, state: state, error: lastError, lastSyncedAt: lastSyncedAt,
      user: user ? { id: user.id, email: user.email || "", name: user.name || user.email || "" } : null,
      pending: user ? pendingCount() : 0
    };
  }
  function setState(s) {
    state = s;
    emit("status", status());
  }
  function isOfflineError(msg) {
    return navigator.onLine === false || /^(offline|timeout)$|network|fetch/i.test(msg || "");
  }
  function refreshState() {
    if (!user) return;
    if (Object.keys(inflight).length || Object.keys(timers).length) setState("syncing");
    else if (pendingCount()) setState(lastError ? (isOfflineError(lastError) ? "offline" : "error") : "pending");
    else { lastSyncedAt = Date.now(); lastError = ""; setState("synced"); }
  }

  function handleError(err) {
    var msg = (err && err.message) || String(err);
    lastError = isOfflineError(msg) ? "offline" : msg;
    clearTimeout(retryTimer);
    // An upload the server refused as invalid would only be refused again;
    // the next edit tries anew. Everything else (offline, server busy) retries.
    var refused = err && err.status >= 400 && err.status < 500 && err.status !== 408 && err.status !== 429;
    if (user && !refused) retryTimer = setTimeout(flushDirty, RETRY_DELAY);
  }

  // The server says nobody is signed in any more (session expired, or
  // signed out in another tab). Edits stay here, marked, and upload after
  // the next sign-in.
  function sessionEnded() {
    if (!user) return;
    user = null;
    Object.keys(timers).forEach(function (id) { clearTimeout(timers[id]); delete timers[id]; });
    setState("signed-out");
    notice("sessionExpired", {});
  }

  // --------------------------------------------------------------- pull
  // Keep both versions when a project changed here *and* in the account
  // since this browser last synced: the account's copy keeps the original
  // id, this browser's edits become a new "conflicted copy" project.
  function keepBoth(local, row) {
    var copy = JSON.parse(JSON.stringify(local));
    copy.id = TB.uid("proj");
    copy.title = local.title + " (conflicted copy, " + new Date().toLocaleDateString() + ")";
    copy.demoVersion = undefined;
    TB.writeProjectLocal(copy);
    patchMeta(copy.id, { dirty: true, rev: 1 });
    patchMeta(local.id, { remoteRev: row.rev, dirty: false, sourcesHash: writeFromRow(row) });
    schedulePush(copy.id);
    return { id: local.id, title: local.title, copyId: copy.id, copyTitle: copy.title };
  }

  // Returns { conflicts, written: [ids replaced from the account] }.
  function applyPull(heads, full) {
    var meta = readMeta();
    var seen = {};
    var conflicts = [];
    var written = [];
    heads.forEach(function (head) {
      seen[head.id] = true;
      var m = meta[head.id] || {};
      if (m.localOnly) return;
      var local = TB.loadProject(head.id);
      // "Changed here" = edited since the last sync, or never synced at all
      // (its relation to the account's copy is unknown) unless it is the
      // untouched demo every fresh browser seeds.
      var changedHere = !!local && (!!m.dirty || (m.remoteRev == null && !isUntouchedDemo(local)));
      if (head.deleted) {
        if (head.id === TB.DEMO_PROJECT_ID && TB.markDemoSeeded) TB.markDemoSeeded();
        if (local && changedHere && m.remoteRev !== head.rev) {
          // Deleted elsewhere but edited here: keep the work; the next
          // upload restores it to the account.
          patchMeta(head.id, { remoteRev: head.rev, dirty: true, sourcesHash: null });
          return;
        }
        if (local) TB.removeProjectLocal(head.id);
        dropMeta(head.id);
        return;
      }
      var row = full[head.id];
      if (!usableRow(row)) return;                // already up to date here (or unreadable)
      // Deleted here (e.g. offline) and unchanged in the account since:
      // the pending upload delivers the deletion, so don't bring it back.
      if (!local && m.dirty && m.remoteRev === row.rev) return;
      if (!local || !changedHere) {
        patchMeta(head.id, { remoteRev: row.rev, dirty: false, sourcesHash: writeFromRow(row) });
        written.push(head.id);
        return;
      }
      conflicts.push(keepBoth(local, row));
      written.push(head.id);
    });
    // Synced before but gone from the account altogether.
    TB.listProjects().forEach(function (p) {
      var m = meta[p.id];
      if (m && m.remoteRev != null && !m.localOnly && !m.dirty && !seen[p.id]) {
        TB.removeProjectLocal(p.id);
        dropMeta(p.id);
      }
    });
    return { conflicts: conflicts, written: written };
  }

  function fetchFull(ids) {
    var batches = [];
    for (var i = 0; i < ids.length; i += 40) batches.push(ids.slice(i, i + 40));
    return Promise.all(batches.map(function (batch) {
      return request("GET", PROJECTS_API + "?ids=" + batch.map(encodeURIComponent).join(","), undefined, DOWNLOAD_TIMEOUT)
        .then(expectOk).then(function (data) { return data.projects || []; });
    })).then(function (lists) { return [].concat.apply([], lists); });
  }

  // Two steps so that opening a page usually transfers only a short list
  // of ids and revisions; full projects are fetched only when they changed
  // in the account.
  function pullAll() {
    return request("GET", PROJECTS_API).then(expectOk).then(function (data) {
      var heads = data.projects || [];
      var meta = readMeta();
      var need = heads.filter(function (h) {
        var m = meta[h.id] || {};
        if (h.deleted || m.localOnly) return false;
        if (m.remoteRev !== h.rev) return true;
        return !TB.loadProject(h.id) && !m.dirty;
      }).map(function (h) { return h.id; });
      if (!need.length) return applyPull(heads, {});
      return fetchFull(need).then(function (rows) {
        var full = {};
        rows.forEach(function (r) { full[r.id] = r; });
        return applyPull(heads, full);
      });
    }).then(function (result) {
      lastSyncedAt = Date.now();
      result.conflicts.forEach(function (c) { notice("conflict", c); });
      return result;
    });
  }

  // --------------------------------------------------------------- push
  function schedulePush(id, delay) {
    if (!user) return;
    clearTimeout(timers[id]);
    timers[id] = setTimeout(function () { delete timers[id]; push(id); }, delay === undefined ? PUSH_DELAY : delay);
    setState("syncing");
  }

  // Resolves { rev, direct } — direct when this browser's version is what
  // the account now holds; otherwise reconcile() already updated the browser
  // copy and its sync record ({ rev, restored } after a refused delete).
  function upload(id, body, base, attempt) {
    var payload = Object.assign({}, body, { base: base == null ? null : base, writer: writerId() });
    return request("PUT", projectUrl(id), payload).then(function (res) {
      if (res.status === 200 || res.status === 201) return { rev: res.data.rev, direct: true };
      if (res.status === 409) return reconcile(id, body, res.data.current || null, (attempt || 0) + 1);
      throw httpError(res.status, res.data);
    });
  }

  // The project changed (or vanished) in the account since this browser
  // last synced it; `remote` is the account's copy (null if gone).
  function reconcile(id, body, remote, attempt) {
    if (attempt > 3) throw new Error("The project keeps changing on another computer — will try again shortly.");
    if (!remote) {
      return body.deleted ? { rev: null, direct: true } : upload(id, withSources(id, body), null, attempt);
    }
    if (remote.deleted || !usableRow(remote)) {
      // Deleted elsewhere: our delete is moot; our edits bring it back.
      return body.deleted ? { rev: remote.rev, direct: true } : upload(id, withSources(id, body), remote.rev, attempt);
    }
    if (body.deleted) {
      // Edited elsewhere after this browser last saw it: don't delete
      // someone's newer work — restore it here instead.
      patchMeta(id, { sourcesHash: writeFromRow(remote) });
      notice("restored", { id: id, title: remote.title });
      return { rev: remote.rev, restored: true };
    }
    var local = TB.loadProject(id);
    if (!local || isUntouchedDemo(local)) {
      patchMeta(id, { sourcesHash: writeFromRow(remote) });
      return { rev: remote.rev, direct: false };
    }
    notice("conflict", keepBoth(local, remote));
    return { rev: remote.rev, direct: false };
  }

  function push(id) {
    if (!user) return;
    if (inflight[id]) { again[id] = true; return; }
    var m = getMeta(id);
    if (!m || !m.dirty || m.localOnly) { refreshState(); return; }
    var rev = m.rev || 0;
    var project = TB.loadProject(id);
    var built = bodyFor(project, m);
    inflight[id] = upload(id, built.body, m.remoteRev).then(function (result) {
      var stillDirty = ((getMeta(id) || {}).rev || 0) !== rev;
      if (result.restored) {
        patchMeta(id, { remoteRev: result.rev, dirty: false });
      } else if (!project) {
        dropMeta(id);                                    // deletion delivered
      } else if (result.direct) {
        patchMeta(id, { remoteRev: result.rev, dirty: stillDirty, sourcesHash: built.hash });
      } else {
        patchMeta(id, { remoteRev: result.rev, dirty: stillDirty });
      }
      lastError = "";
    }, handleError).then(function () {
      delete inflight[id];
      if (again[id]) { delete again[id]; push(id); }
      refreshState();
    });
  }

  function flushDirty() {
    if (!user) return;
    var m = readMeta();
    Object.keys(m).forEach(function (id) {
      if (m[id].dirty && !m[id].localOnly && !timers[id]) push(id);
    });
    refreshState();
  }

  function flushAndWait(ms) {
    Object.keys(timers).forEach(function (id) { clearTimeout(timers[id]); delete timers[id]; });
    flushDirty();
    var deadline = Date.now() + ms;
    return new Promise(function (resolve) {
      (function check() {
        if (!Object.keys(inflight).length || Date.now() > deadline) return resolve();
        setTimeout(check, 100);
      })();
    });
  }

  // Every save/delete marks the project for upload. Projects this browser
  // already tracks stay marked even while signed out (e.g. a session that
  // ended), so the edits upload after the next sign-in.
  TB.onProjectChange(function (type, id) {
    if (!enabled) return;
    var m = getMeta(id);
    if (!m && !user) return;
    if (m && m.localOnly) return;
    if (type === "delete" && !(m && m.remoteRev != null)) { dropMeta(id); return; }
    patchMeta(id, { dirty: true, rev: ((m && m.rev) || 0) + 1 });
    schedulePush(id);
  });

  // ------------------------------------------------------------ session
  // Remove an account's synced copies from this browser. Unsynced edits are
  // kept as browser-only projects rather than lost.
  function forgetAccountData(includeUnsynced) {
    var m = readMeta();
    Object.keys(m).forEach(function (id) {
      if (m[id].localOnly) return;
      if (m[id].dirty && !includeUnsynced && TB.loadProject(id)) { m[id] = { localOnly: true }; return; }
      TB.removeProjectLocal(id);
      delete m[id];
    });
    writeMeta(m);
    localStorage.removeItem(OWNER_KEY);
    if (TB.forgetDemoSeed) TB.forgetDemoSeed();
  }

  // Nobody is signed in but this browser still holds an account's copies
  // (e.g. they logged out from the SST website's menu): don't leave them
  // readable here. They're safe in the account. Edits that never reached it
  // stay marked, so they upload when the same person signs in again.
  function forgetSyncedCopies() {
    var m = readMeta();
    var unsynced = false;
    Object.keys(m).forEach(function (id) {
      if (m[id].localOnly) return;
      if (m[id].dirty && TB.loadProject(id)) { unsynced = true; return; }
      TB.removeProjectLocal(id);
      delete m[id];
    });
    writeMeta(m);
    if (!unsynced) localStorage.removeItem(OWNER_KEY);
    if (TB.forgetDemoSeed) TB.forgetDemoSeed();
  }

  function startSession() {
    var owner = localStorage.getItem(OWNER_KEY);
    if (owner && owner !== String(user.id)) forgetAccountData(false);
    localStorage.setItem(OWNER_KEY, String(user.id));
    setState("syncing");
    return pullAll().then(function (result) {
      // A fresh browser (or one whose open project was deleted elsewhere)
      // has no project open: open the most recently changed one.
      if (!TB.getActiveProject()) {
        var latest = TB.listProjects()[0];
        if (latest) {
          TB.setActiveProjectId(latest.id);
          result.written.push(latest.id);
        }
      }
      var m = readMeta();
      var demo = TB.loadProject(TB.DEMO_PROJECT_ID);
      if (demo && !m[demo.id]) patchMeta(demo.id, { dirty: true, rev: 1 });
      flushDirty();
      var unsynced = TB.listProjects().filter(function (p) { return !m[p.id] && p.id !== TB.DEMO_PROJECT_ID; });
      if (unsynced.length) emit("importNeeded", unsynced);
      return result;
    });
  }

  var drawn = false;   // the page already drew from the browser copy
  function boot() {
    if (!enabled) return Promise.resolve();
    if (!user) {
      if (localStorage.getItem(OWNER_KEY)) forgetSyncedCopies();
      booted = true;
      return Promise.resolve();
    }
    return startSession().then(function (result) {
      refreshState();
      // A slow download finished after the page drew: offer a reload if the
      // project on screen changed.
      var active = TB.getActiveProjectId();
      if (drawn && active && result.written.indexOf(active) !== -1) notice("remoteChange", { id: active });
    }, function (err) {
      handleError(err);
      if (user) setState(lastError === "offline" ? "offline" : "error");
    }).then(function () { booted = true; });
  }

  var started = boot();
  TB.setReady(Promise.race([started, new Promise(function (resolve) {
    setTimeout(function () { drawn = true; resolve(); }, READY_WAIT);
  })]));

  window.addEventListener("online", flushDirty);
  // Coming back to a tab: tell the page if its project changed on another
  // computer meanwhile (the page shows stale data until reloaded).
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible" || !user || !booted) return;
    flushDirty();
    var id = TB.getActiveProjectId();
    var m = id && getMeta(id);
    if (!m || m.remoteRev == null || m.localOnly) return;
    request("GET", projectUrl(id) + "?head=1").then(function (res) {
      if (res.status !== 200) return;
      var cur = getMeta(id) || {};
      if (res.data.rev !== cur.remoteRev && !inflight[id] && !timers[id]) emit("remoteChange", { id: id, deleted: res.data.deleted });
    }).catch(function () {});
  });

  // ------------------------------------------------------------ account
  // Signing out removes this account's projects from the browser (they are
  // safe in the account), so the next person at a shared computer can't
  // open them, then signs out on the server and opens the sign-in page.
  // Resolves false if the user chose to stay signed in.
  function signOut() {
    if (!user) return Promise.resolve(true);
    return flushAndWait(8000).then(function () {
      if (pendingCount() && !window.confirm("Some changes haven't reached your account yet (you may be offline). Signing out now removes them from this browser. Sign out anyway?")) {
        return false;
      }
      forgetAccountData(true);
      user = null;
      var form = document.createElement("form");
      form.method = "post";
      form.action = urls.logout;
      [["csrfmiddlewaretoken", csrfToken()], ["next", urls.welcome]].forEach(function (pair) {
        var input = document.createElement("input");
        input.type = "hidden";
        input.name = pair[0];
        input.value = pair[1];
        form.appendChild(input);
      });
      document.body.appendChild(form);
      form.submit();
      return true;
    });
  }

  // Answer to "importNeeded": add these browser-only projects to the
  // account, or keep them on this browser only.
  function adopt(ids) {
    ids.forEach(function (id) { patchMeta(id, { dirty: true, rev: 1, localOnly: false }); });
    flushDirty();
  }
  function keepLocal(ids) {
    ids.forEach(function (id) { patchMeta(id, { localOnly: true }); });
  }

  // "cloud" | "pending" | "local" for a project, or null when not signed in.
  function syncState(id) {
    if (!enabled || !user) return null;
    var m = getMeta(id);
    if (!m || m.localOnly) return "local";
    return m.dirty ? "pending" : "cloud";
  }

  TB.cloud = {
    enabled: function () { return enabled; },
    status: status, on: on, signOut: signOut,
    adopt: adopt, keepLocal: keepLocal, syncState: syncState, flush: flushDirty
  };
})();
