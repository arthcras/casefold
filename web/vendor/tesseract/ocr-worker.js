// Tesseract's worker, with one change: the language data is served as base64 text (eng.traineddata.gz.b64.txt), because the
// page's host serves only common web file types. This wrapper fetches that text and hands Tesseract the gzip bytes it expects.
const _fetch = self.fetch.bind(self);
self.fetch = async (url, opts) => {
  const u = String(url);
  if (!/\.traineddata\.gz$/.test(u)) return _fetch(url, opts);
  const r = await _fetch(u + '.b64.txt', opts);
  if (!r.ok) return r;
  const bin = atob((await r.text()).trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Response(bytes, { status: 200, headers: { 'Content-Type': 'application/octet-stream' } });
};
importScripts('worker.min.js');
