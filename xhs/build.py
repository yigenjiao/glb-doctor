#!/usr/bin/env python3
"""
从仓库根目录的 index.html 生成小红书「小工具」版本，输出 dist/glb-doctor-xhs.zip。

小红书小工具要求：纯前端、离线可用、不能发起外部网络请求。
这个脚本对原页面做这些改动（原文件不动）：
  1. 去掉 Google Fonts，改用系统字体
  2. 顶栏 GitHub 链接改成纯文字（小工具里不要跳站外）
  3. 两个样本 GLB 以 base64 内嵌，不再 fetch
  4. 「下载修复文件」「导出报告」改走保存面板：系统分享 / 下载 / 复制报告文本
     （App 内置浏览器常常不响应 <a download>）
  5. 「拖进来」类文案改成手机上的「选择」
  6. 只打包运行需要的文件（不含 docs、README、样本生成脚本）

用法：python3 xhs/build.py
"""
import base64, re, shutil, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'dist' / 'xhs'
ZIP = ROOT / 'dist' / 'glb-doctor-xhs.zip'

html = (ROOT / 'index.html').read_text(encoding='utf-8')


def sub(old, new, count=1, regex=False):
    """替换，并且确认原文里真的有这段，避免原版改动后静默失效。"""
    global html
    if regex:
        html, n = re.subn(old, new, html, count=0 if count == 0 else count, flags=re.S)
    else:
        n = html.count(old)
        html = html.replace(old, new) if count == 0 else html.replace(old, new, count)
    if n == 0:
        sys.exit(f'构建失败：index.html 里找不到要替换的内容：\n  {old[:120]}')


# 1. 字体
sub(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*'
    r'<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\s*'
    r'<link href="https://fonts\.googleapis\.com/css2[^"]*" rel="stylesheet">\s*', '', regex=True)
sub('--mono:"JetBrains Mono",ui-monospace,monospace;',
    '--mono:ui-monospace,"SF Mono",Menlo,Consolas,"Roboto Mono",monospace;')
sub('--sans:"Noto Sans SC",system-ui,-apple-system,sans-serif;',
    '--sans:system-ui,-apple-system,"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;')
# 系统中文字体 300 字重在部分安卓机上会很细，统一用常规
sub('font-family:var(--sans);font-weight:300;', 'font-family:var(--sans);font-weight:400;')

# 2. 外链
sub(r'<a class="brand" href="https://github\.com/[^"]*">(.*?)</a>', r'<span class="brand">\1</span>', regex=True)
sub('<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">\n', '')

# 3. 内嵌样本
samples = {n: base64.b64encode((ROOT / 'samples' / n).read_bytes()).decode()
           for n in ('broken.glb', 'healthy.glb')}
sub("""    const res = await fetch('samples/' + name);
    if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
    const ab = await res.arrayBuffer();""",
    """    const b64 = SAMPLES[name];
    if (!b64) throw new Error('没有这个样本');
    const ab = Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;""")
sub('async function loadSample(name) {',
    'const SAMPLES = ' + repr(samples).replace("'", '"') + ';\nasync function loadSample(name) {')

# 4. 保存面板
SAVE_CSS = """
/* ---------- 保存面板（小红书版） ---------- */
.save{position:fixed;inset:0;z-index:20;display:none;align-items:flex-end;justify-content:center;background:rgba(0,0,0,.55)}
.save.on{display:flex}
.save .sheet{width:100%;max-width:520px;background:var(--bg-2);border:1px solid var(--line-2);border-bottom:0;border-radius:16px 16px 0 0;padding:18px 18px calc(18px + env(safe-area-inset-bottom))}
.save h3{font-size:15px;font-weight:500;margin-bottom:4px}
.save .nm{font-family:var(--mono);font-size:11.5px;color:var(--faint);word-break:break-all;margin-bottom:12px}
.save .acts{display:flex;flex-direction:column;gap:8px}
.save .acts .btn{justify-content:center;padding:11px 14px;font-size:13px}
.save .note{margin-top:12px;font-size:12px;line-height:1.8;color:var(--muted)}
.save .msg{margin-top:8px;font-size:12px;color:var(--ok);min-height:1em}
/* 手机竖屏：欢迎框收紧，未加载模型时隐藏视图工具栏 */
@media (max-width:860px){
  .drop{padding:12px;overflow:auto}
  .drop .box{padding:18px 16px;border-radius:14px}
  .drop .cat{width:76px;margin:0 auto 6px}
  .drop h2{font-size:17px;margin-bottom:6px}
  .drop p{font-size:12px;line-height:1.7}
  .drop .row{margin-top:12px}
  .drop .priv{margin-top:10px}
  .stage:has(#drop:not([style*="none"])) .toolbar,
  .stage:has(#drop:not([style*="none"])) .hud{display:none}
}
"""
sub('</style>', SAVE_CSS + '</style>')

SAVE_HTML = """
<div class="save" id="save"><div class="sheet">
  <h3 id="saveTitle">保存文件</h3>
  <div class="nm" id="saveName"></div>
  <div class="acts">
    <button class="btn primary" id="saveShare">发送到 / 存到文件</button>
    <button class="btn" id="saveDl">直接下载</button>
    <button class="btn" id="saveCopy">复制报告全文</button>
    <button class="btn" id="saveClose">关闭</button>
  </div>
  <div class="msg" id="saveMsg"></div>
  <div class="note" id="saveNote">如果点了没反应，说明当前 App 不允许网页保存文件。可以把这个小工具分享到浏览器里打开再保存，或者用电脑浏览器访问网站版。</div>
</div></div>
"""
sub('<div class="zoom" id="zoom">', SAVE_HTML + '<div class="zoom" id="zoom">')

SAVE_JS = """
/* ---------- 保存面板（小红书版） ---------- */
function saveFile(blob, name, text) {
  const box = $('#save'), msg = $('#saveMsg');
  $('#saveTitle').textContent = text ? '导出体检报告' : '保存修复后的文件';
  $('#saveName').textContent = name + ' · ' + fmtBytes(blob.size);
  msg.textContent = '';
  let file = null;
  try { file = new File([blob], name, { type: blob.type || 'application/octet-stream' }); } catch (e) {}
  const canShare = !!(file && navigator.canShare && navigator.canShare({ files: [file] }));
  $('#saveShare').style.display = canShare ? '' : 'none';
  $('#saveCopy').style.display = text ? '' : 'none';
  $('#saveShare').onclick = async () => {
    try { await navigator.share({ files: [file], title: name }); msg.textContent = '已交给系统处理'; }
    catch (e) { if (e.name !== 'AbortError') msg.textContent = '分享失败：' + e.message; }
  };
  $('#saveDl').onclick = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    msg.textContent = '已发起下载，没看到的话请看下方说明';
  };
  $('#saveCopy').onclick = async () => {
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (e) {}
    if (!ok) {
      const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(t); t.select();
      try { ok = document.execCommand('copy'); } catch (e) {}
      t.remove();
    }
    msg.textContent = ok ? '已复制，可以粘贴到备忘录或发给同事' : '复制失败，请换用下载';
  };
  $('#saveClose').onclick = () => box.classList.remove('on');
  box.onclick = e => { if (e.target === box) box.classList.remove('on'); };
  box.classList.add('on');
}
"""
sub('async function loadSample(name) {', SAVE_JS + 'async function loadSample(name) {', count=1)

# 修复文件下载
sub("if (dl) dl.onclick = () => { const a = document.createElement('a'); a.href = state.fixInfo.url; a.download = state.fileName; a.click(); };",
    "if (dl) dl.onclick = () => saveFile(state.fixInfo.blob, state.fileName);")
sub("const url = URL.createObjectURL(new Blob([ab], { type: 'model/gltf-binary' }));",
    "const blob = new Blob([ab.slice(0)], { type: 'model/gltf-binary' }); const url = URL.createObjectURL(blob);")
sub("{ fixInfo: { done, url } }", "{ fixInfo: { done, url, blob } }")
sub('<button class="btn primary" id="btnFixDl">下载 ${esc(state.fileName)}</button>',
    '<button class="btn primary" id="btnFixDl">保存 ${esc(state.fileName)}</button>')
# 报告导出
sub("""  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\\n')], { type: 'text/markdown' }));
  a.download = state.fileName.replace(/\\.(glb|gltf)$/i, '') + '.report.md';
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);""",
    """  const text = lines.join('\\n');
  saveFile(new Blob([text], { type: 'text/markdown' }), state.fileName.replace(/\\.(glb|gltf)$/i, '') + '.report.md', text);""")

# 5. 手机文案
sub('<h2>把 GLB 拖进来，香蕉猫帮你查</h2>', '<h2>选一个 GLB，香蕉猫帮你查</h2>')
sub('或把 <b>.gltf + .bin + 贴图</b> 一起拖进来。', '或把 <b>.gltf + .bin + 贴图</b> 一起选上。')
sub('能修的问题可以一键修复，下载修好的新文件。', '能修的问题可以一键修复，保存修好的新文件。')
sub('把 <code>.glb</code> 拖到右边，或者先点「看坏样本」看看它能查出什么。',
    '点「选择文件」打开 <code>.glb</code>，或者先点「看坏样本」看看它能查出什么。')
sub('// 全部在本地浏览器里解析，文件不会上传', '// 全部在手机本地解析，文件不会上传')

# 自检：不能残留外部地址（注释和 alert 文本外）
leftover = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']+', html) + re.findall(r'fetch\(\s*["\']https?://', html)
if leftover:
    sys.exit('构建失败：还有外部请求 ' + repr(leftover))

# 6. 输出
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
(OUT / 'index.html').write_text(html, encoding='utf-8')
(OUT / 'assets').mkdir()
for n in ('banana-cat.webp', 'favicon.png'):
    shutil.copy2(ROOT / 'assets' / n, OUT / 'assets' / n)
shutil.copytree(ROOT / 'vendor', OUT / 'vendor')
shutil.copy2(ROOT / 'LICENSE', OUT / 'LICENSE')

ZIP.unlink(missing_ok=True)
with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():
            z.write(p, p.relative_to(OUT).as_posix())  # index.html 在 zip 根目录
print(f'OK  {ZIP.relative_to(ROOT)}  {ZIP.stat().st_size / 1024:.0f} KB')
