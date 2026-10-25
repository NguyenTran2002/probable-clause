// The page's figures (config.json, from api/settings.py) and the corpus summary (corpus.json), both static files
// beside the page (contract §11.3). Fetched relative to the page, so they work under any path prefix.

export async function loadStatic() {
  const get = async path => {
    const r = await fetch(path, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  };
  const [cfg, corpus] = await Promise.all([get('config.json'), get('corpus.json')]);
  return { cfg, corpus };
}

// The recorded runs (T5.6), from the web service, never the API (brief §7.4). None yet is not an error.
export async function loadReplays() {
  try {
    const r = await fetch('replays/index.json', { cache: 'no-cache' });
    if (!r.ok) return [];
    const list = await r.json();
    return Array.isArray(list) ? list : [];
  } catch { return []; }
}

export async function loadReplay(slug) {
  const r = await fetch(`replays/${encodeURIComponent(slug)}.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`replay ${slug}: ${r.status}`);
  return r.json();
}
