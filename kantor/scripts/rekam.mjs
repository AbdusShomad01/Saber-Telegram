// Merekam timelapse Kantor AI jadi MP4 (vertikal 1080×1920, 30 fps), frame demi frame, jadi hasilnya mulus.
// Jalankan `npm run dev` dulu, lalu: npm run rekam -- kantor-ai.mp4 [--w 1080 --h 1920 --fps 30 --detik 30 --gaya clay]
// Butuh Google Chrome (atau CHROME=/path/ke/chrome) dan ffmpeg (brew install ffmpeg, atau FFMPEG=/path/ke/ffmpeg).
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const arg = (k, d) => {
  const i = process.argv.indexOf(`--${k}`);
  return i > 0 ? process.argv[i + 1] : d;
};
const out = path.resolve(process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : 'kantor-ai.mp4');
const W = Number(arg('w', 1080));
const H = Number(arg('h', 1920));
const FPS = Number(arg('fps', 30));
const SECONDS = Number(arg('detik', 30));
const BASE = arg('url', 'http://localhost:5173');
const GAYA = arg('gaya', '');
const home = os.homedir();
const CHROME =
  process.env.CHROME ??
  [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
  ].find((p) => fs.existsSync(p));
const FFMPEG = process.env.FFMPEG ?? 'ffmpeg';
if (!CHROME) throw new Error('Chrome tidak ditemukan (set CHROME=/path/ke/chrome)');

const frames = fs.mkdtempSync(path.join(os.tmpdir(), 'kantor-frames-'));
const port = 9333;
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'kantor-chrome-'))}`, '--no-first-run', '--hide-scrollbars', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', `--window-size=${W},${H}`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let list;
  for (let i = 0; i < 50 && !list; i++) {
    await sleep(200);
    list = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json()).catch(() => null);
  }
  const page = list.find((t) => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const waiting = new Map();
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && waiting.has(m.id)) {
      waiting.get(m.id)(m);
      waiting.delete(m.id);
    }
  };
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const n = ++id;
      waiting.set(n, (m) => (m.error ? reject(new Error(`${method}: ${m.error.message}`)) : resolve(m.result)));
      ws.send(JSON.stringify({ id: n, method, params }));
    });
  const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value;
  const until = async (expression, what, ms = 20000) => {
    for (const end = Date.now() + ms; Date.now() < end; await sleep(250)) if (await evaluate(expression)) return;
    throw new Error(`timeout: ${what}`);
  };

  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `${BASE}/?timelapse=1&rekam=1${GAYA ? `&gaya=${encodeURIComponent(GAYA)}` : ''}` });
  await until(`typeof window.__koFrame === 'function' && window.__koFrame(0)`, 'scene');
  await sleep(1200);

  const total = Math.round(SECONDS * FPS);
  for (let f = 0; f < total; f++) {
    await evaluate(`window.__koFrame(${f / FPS})`);
    const { data } = await send('Page.captureScreenshot', { format: 'jpeg', quality: 92 });
    fs.writeFileSync(path.join(frames, `${String(f).padStart(5, '0')}.jpg`), Buffer.from(data, 'base64'));
    if (f % FPS === 0) process.stdout.write(`\r${f}/${total} frame`);
  }
  process.stdout.write('\n');
  ws.close();
  const r = spawnSync(FFMPEG, ['-y', '-framerate', String(FPS), '-i', path.join(frames, '%05d.jpg'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-movflags', '+faststart', out], { stdio: 'inherit', env: { ...process.env, DYLD_LIBRARY_PATH: FFMPEG.includes('/') ? path.dirname(FFMPEG) : process.env.DYLD_LIBRARY_PATH } });
  if (r.status !== 0) throw new Error('ffmpeg gagal');
  console.log(`Selesai: ${out}`);
} finally {
  chrome.kill();
  fs.rmSync(frames, { recursive: true, force: true });
}
