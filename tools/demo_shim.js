// Static-demo backend: answers the dashboard's /api/* calls in the browser.
//
// Every vehicle state and every remote-action result was computed ahead of
// time by tools/build_demo.py, using the real Python rules engine, root-cause
// correlator and action runner against the simulator. This file only replays
// them, plus ports of the flight-log analyzer and fleet correlator so uploaded
// logs and the fleet-pattern banners work live.
(() => {
  const D = window.DEMO;
  const byName = Object.fromEntries(D.vehicles.map(v => [v.name, v]));
  const cur = Object.fromEntries(D.vehicles.map(v => [v.name, v.start]));
  const pending = {};
  const audit = D.audit.slice();
  const t0 = Date.now() / 1000;
  const clone = o => JSON.parse(JSON.stringify(o));
  const sortedJson = o => JSON.stringify(Object.fromEntries(Object.entries(o || {}).sort()));

  function entry(v) {
    const r = clone(v.states[cur[v.name]].result);
    const elapsed = Date.now() / 1000 - t0;
    const age = v.meta.silent ? v.meta.age_s + elapsed : v.meta.age_s + (elapsed % 7);
    if (v.meta.silent && r.findings[0]) r.findings[0].title = `No heartbeat for ${Math.round(age)}s`;
    return { ...r, ...v.meta, age_s: +age.toFixed(1), pending_commands: (pending[v.name] || 0) };
  }

  function runAction(req) {
    const v = byName[req.drone];
    if (!v) return [404, { error: 'unknown vehicle' }];
    const base = `${v.states[cur[v.name]].fkey}|${req.action}|`;
    const tr = v.transitions[base + sortedJson(req.params)] || v.transitions[base + '*'];
    const now = Date.now() / 1000;
    const meta = { ts: now, vehicle: v.name, action: req.action, params: req.params || {},
                   operator: 'you (demo)', ticket: req.ticket || '', reason: req.reason || '' };
    if (!tr) return [200, { ...meta, ok: false, status: 'failed', error: 'Not available in this demo' }];
    const rec = { ...clone(tr.record), ...meta };
    if (v.meta.mode === 'pull') {
      cur[v.name] = tr.next;
      audit.unshift({ ...rec, via: 'direct' });
      return [200, rec];
    }
    // Push vehicle: the command waits in its mailbox until its next check-in.
    pending[v.name] = (pending[v.name] || 0) + 1;
    const queued = { ...meta, status: 'queued', via: 'mailbox', expires: now + 300 };
    audit.unshift(queued);
    if (!v.meta.silent) {
      setTimeout(() => {
        cur[v.name] = tr.next;
        pending[v.name]--;
        audit.unshift({ ...rec, ts: Date.now() / 1000, via: 'mailbox' });
      }, 4000);
    }
    return [202, queued];
  }

  // Vehicles mid-way through self-healing play their remaining steps live.
  setInterval(() => {
    for (const v of D.vehicles) {
      const seq = v.meta.auto_seq || [];
      const i = seq.indexOf(cur[v.name]);
      if (i < 0 || i + 1 >= seq.length) continue;  // finished, or an operator stepped in
      cur[v.name] = seq[i + 1];
      const rec = v.states[seq[i + 1]].auto_new;
      if (rec) audit.unshift({ ...rec, ts: Date.now() / 1000 });
    }
  }, 9000);

  // ---- port of fleetdebug/fleetcorr.py
  const SIGNATURES = [
    ['gnss', ['gps', 'satellite', 'hdop', 'pos_horiz']],
    ['cellular', ['cellular', 'unreachable', 'no heartbeat for', 'cannot reach']],
    ['weather', ['wind', 'precipitation']],
    ['power', ['mains power', 'under-voltage']],
    ['compass', ['compass', 'mag']],
    ['software-crash', ['not running', 'python error', 'traceback', 'failed']],
    ['memory', ['memory', 'oom']],
    ['upload', ['not reaching the cloud']],
    ['thermal', ['°c', 'climate']],
  ];
  const SITE_HINTS = D.site_hints;
  const signature = f => {
    const text = (f.title + ' ' + (f.detail || '')).toLowerCase();
    const hit = SIGNATURES.find(([, words]) => words.some(w => text.includes(w)));
    return hit ? hit[0] : null;
  };
  function correlate(results) {
    const out = [];
    for (const [key, label] of [['site', 'site'], ['version', 'software version']]) {
      const groups = {};
      for (const r of results) {
        const g = key === 'site' ? r.site : r.snapshot?.software?.version;
        if (g) (groups[g] ||= []).push(r);
      }
      for (const [g, members] of Object.entries(groups)) {
        const hits = {};
        for (const r of members) for (const f of r.findings || []) {
          if (f.severity !== 'critical' && f.severity !== 'warning') continue;
          const sig = signature(f);
          if (sig) (hits[sig] ||= new Set()).add(r.name);
        }
        for (const [sig, vs] of Object.entries(hits)) {
          if (key === 'version' && ['weather', 'cellular', 'power', 'gnss'].includes(sig)) continue;
          if (key === 'site' && ['software-crash', 'memory'].includes(sig)) continue;
          const share = vs.size / members.length;
          if (vs.size >= 2 && share >= 0.5) {
            out.push({ scope: label, group: g, signature: sig, vehicles: [...vs].sort(),
                       share: +share.toFixed(2),
                       hint: key === 'site' ? (SITE_HINTS[sig] || '') :
                         `Common to vehicles on ${g}: suspect a software regression. Pause the rollout and compare against the previous version.` });
          }
        }
      }
    }
    return out.sort((a, b) => b.vehicles.length - a.vehicles.length || a.scope.localeCompare(b.scope));
  }

  // ---- port of fleetdebug/logs.py
  const CHECKS = D.log_checks;
  const CRIT_WORDS = ['failsafe', 'abort', 'rtl', 'land', 'parachute', 'crash', 'emergency', 'ekf', 'lost'];
  function parseCsv(text) {
    const lines = text.trim().split(/\r?\n/);
    const hdr = lines[0].split(',').map(h => h.trim());
    return lines.slice(1).map(l => {
      const cells = l.split(','), row = {};
      hdr.forEach((h, i) => {
        const c = (cells[i] ?? '').trim();
        row[h] = c !== '' && !isNaN(Number(c)) ? Number(c) : c;
      });
      return row;
    });
  }
  const ev = (severity, title, field, start, end, worst, threshold) => ({
    severity, title, field, start_s: start, end_s: end, duration_s: +(end - start).toFixed(1),
    worst: +worst.toFixed(2), threshold });
  function analyze(rows) {
    if (!rows.length) return { summary: 'empty log', events: [], stats: {}, timeline: [] };
    const events = [];
    for (const [field, [op, thr, sev, msg]] of Object.entries(CHECKS)) {
      let start = null, worst = null;
      for (const r of rows) {
        const v = r[field];
        const bad = typeof v === 'number' && (op === '>' ? v > thr : v < thr);
        if (bad) {
          if (start === null) { start = r.time_s; worst = v; }
          worst = op === '>' ? Math.max(worst, v) : Math.min(worst, v);
        } else if (start !== null) { events.push(ev(sev, msg, field, start, r.time_s, worst, thr)); start = null; }
      }
      if (start !== null) events.push(ev(sev, msg, field, start, rows[rows.length - 1].time_s, worst, thr));
    }
    let prev = null;
    for (const r of rows) {
      const v = r.battery_voltage;
      if (typeof v !== 'number') continue;
      if (prev && prev[1] - v > 1.0 && r.time_s - prev[0] <= 2)
        events.push(ev('critical', 'Battery voltage sag', 'battery_voltage', prev[0], r.time_s, v, +(prev[1] - 1).toFixed(2)));
      prev = [r.time_s, v];
    }
    for (let i = 1; i < rows.length; i++) {
      const gap = rows[i].time_s - rows[i - 1].time_s;
      if (gap > 2) events.push(ev('warning', 'Telemetry gap', 'time_s', rows[i - 1].time_s, rows[i].time_s, gap, 2));
    }
    events.sort((a, b) => a.start_s - b.start_s);
    const timeline = [];
    let prevMode = null;
    for (const r of rows) {
      if (typeof r.mode === 'string' && r.mode && r.mode !== prevMode) {
        timeline.push({ time_s: r.time_s, type: 'mode', text: r.mode,
                        critical: CRIT_WORDS.slice(0, 3).some(w => r.mode.toLowerCase().includes(w)) });
        prevMode = r.mode;
      }
      if (typeof r.event === 'string' && r.event)
        timeline.push({ time_s: r.time_s, type: 'event', text: r.event,
                        critical: CRIT_WORDS.some(w => r.event.toLowerCase().includes(w)) });
    }
    for (const m of timeline) if (m.critical)
      m.preceded_by = [...new Set(events.filter(e => e.start_s <= m.time_s && e.end_s >= m.time_s - 30)
                                        .map(e => e.title))].sort();
    const stats = {};
    const fields = [...new Set(rows.flatMap(r => Object.keys(r)))].filter(k => k !== 'time_s').sort();
    for (const f of fields) {
      const vals = rows.map(r => r[f]).filter(v => typeof v === 'number');
      if (vals.length) stats[f] = { min: +Math.min(...vals).toFixed(2), max: +Math.max(...vals).toFixed(2),
                                    mean: +(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) };
    }
    const duration = rows[rows.length - 1].time_s - rows[0].time_s;
    const crit = events.filter(e => e.severity === 'critical').length;
    return { summary: `${duration.toFixed(0)}s flight, ${events.length} event(s), ${crit} critical`,
             duration_s: duration, events, timeline, stats };
  }

  // ---- routing
  const json = (status, body) => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' } });
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, opts = {}) => {
    const u = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (!u.pathname.startsWith('/api/')) return realFetch(input, opts);
    const q = Object.fromEntries(u.searchParams);
    const method = (opts.method || 'GET').toUpperCase();
    switch (u.pathname) {
      case '/api/fleet': return json(200, D.vehicles.map(entry));
      case '/api/incidents': return json(200, correlate(D.vehicles.map(entry)));
      case '/api/history': return json(200, D.history);
      case '/api/audit': return json(200, audit);
      case '/api/faults': return json(200, {});
      case '/api/actions': {
        const v = byName[q.drone];
        if (!v) return json(404, { error: 'unknown vehicle' });
        return json(200, { ...v.states[cur[v.name]].catalog, cached: v.meta.mode === 'push' });
      }
      case '/api/logs': {
        const v = byName[q.drone];
        const lines = v ? v.states[cur[v.name]].result.snapshot.journal?.entries || [] : [];
        const mine = lines.filter(l => (q.unit || '').startsWith('mission') ? l.includes('mission') : false);
        return new Response(mine.length ? mine.join('\n') : `-- No entries for ${q.unit} in the last 15 min --`,
                            { status: 200, headers: { 'Content-Type': 'text/plain' } });
      }
      case '/api/action':
        if (method === 'POST') { const [s, b] = runAction(JSON.parse(opts.body || '{}')); return json(s, b); }
        break;
      case '/api/analyze-log':
        if (method === 'POST') {
          const rows = parseCsv(String(opts.body || ''));
          if (rows.length && !('time_s' in rows[0])) return json(400, { error: 'CSV needs a time_s column' });
          return json(200, analyze(rows));
        }
        break;
    }
    return json(404, { error: 'not found' });
  };
})();
