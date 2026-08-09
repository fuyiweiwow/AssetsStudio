from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path


POOL_SCHEMA = "assetslab_hair_random_pool_v1"
VARIANT_SCHEMA = "assetslab_hair_component_variant_v1"
ASSEMBLY_SCHEMA = "assetslab_hair_component_assembly_preview_v1"
COMPONENT_PREVIEW_SCHEMA = "assetslab_hair_component_preview_v1"


def url_path(path: Path, base: Path) -> str:
    relative = Path(os.path.relpath(path.resolve(), base.resolve()))
    return "/".join(html.escape(part, quote=True) for part in relative.parts)


def load_pool(pool_path: Path, component_path: Path) -> list[dict[str, object]]:
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    if pool.get("schema") != POOL_SCHEMA:
        raise RuntimeError(f"unexpected pool schema: {pool_path}")
    catalog = json.loads(component_path.read_text(encoding="utf-8"))
    groups = {item["id"]: item for item in catalog.get("component_groups", [])}
    components = []
    for item in pool.get("components", []):
        group = groups.get(item.get("group_id"), {})
        components.append(
            {
                **item,
                "source_blend": group.get("source_blend", ""),
                "reference_group": item.get("group_id", ""),
            }
        )
    return components


def scan_variants(root: Path, output_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if not root.is_dir():
        return records
    for manifest_path in sorted(root.rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != VARIANT_SCHEMA:
            continue
        candidate = manifest_path.parent
        if not all((candidate / f"{direction}.png").is_file() for direction in ("front", "right", "back", "left")):
            continue
        records.append(
            {
                "id": str(candidate.relative_to(root)).replace("\\", "/"),
                "source_object": manifest.get("source_object", ""),
                "reference_object": manifest.get("reference_object", ""),
                "variant_seed": manifest.get("variant_seed"),
                "variant": manifest.get("variant", {}),
                "compatibility": json.loads((candidate / "compatibility.json").read_text(encoding="utf-8"))
                if (candidate / "compatibility.json").is_file()
                else None,
                "status": manifest.get("status", "component_variant_review_required"),
                "front": url_path(candidate / "front.png", output_dir),
                "right": url_path(candidate / "right.png", output_dir),
                "back": url_path(candidate / "back.png", output_dir),
                "left": url_path(candidate / "left.png", output_dir),
                "blend": url_path(candidate / "actor.blend", output_dir)
                if (candidate / "actor.blend").is_file()
                else "",
            }
        )
    return records


def scan_assemblies(root: Path, output_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if not root.is_dir():
        return records
    for manifest_path in sorted(root.rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != ASSEMBLY_SCHEMA:
            continue
        candidate = manifest_path.parent
        if not all((candidate / f"{direction}.png").is_file() for direction in ("front", "right", "back", "left")):
            continue
        records.append(
            {
                "id": str(candidate.relative_to(root)).replace("\\", "/"),
                "variant_id": manifest.get("variant_id", ""),
                "components": manifest.get("components", []),
                "variant_seed": manifest.get("variant_seed"),
                "status": manifest.get("status", "assembly_review_required"),
                "front": url_path(candidate / "front.png", output_dir),
                "right": url_path(candidate / "right.png", output_dir),
                "back": url_path(candidate / "back.png", output_dir),
                "left": url_path(candidate / "left.png", output_dir),
                "model": url_path(candidate / "model.glb", output_dir)
                if (candidate / "model.glb").is_file()
                else "",
                "blend": url_path(candidate / "actor.blend", output_dir)
                if (candidate / "actor.blend").is_file()
                else "",
            }
        )
    return records


def scan_component_previews(root: Path | None, output_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if root is None or not root.is_dir():
        return records
    for manifest_path in sorted(root.rglob("manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != COMPONENT_PREVIEW_SCHEMA:
            continue
        candidate = manifest_path.parent
        if not all((candidate / f"{direction}.png").is_file() for direction in ("front", "right", "back", "left")):
            continue
        records.append(
            {
                "id": str(candidate.relative_to(root)).replace("\\", "/"),
                "component_id": manifest.get("component_id", ""),
                "source_object": manifest.get("source_object", ""),
                "gender": manifest.get("gender", ""),
                "role": manifest.get("role", ""),
                "fit": manifest.get("fit", {}),
                "front": url_path(candidate / "front.png", output_dir),
                "right": url_path(candidate / "right.png", output_dir),
                "back": url_path(candidate / "back.png", output_dir),
                "left": url_path(candidate / "left.png", output_dir),
            }
        )
    return records


def build_page(output: Path, components: list[dict[str, object]], variants: list[dict[str, object]], assemblies: list[dict[str, object]], previews: list[dict[str, object]]) -> None:
    data = json.dumps({"components": components, "variants": variants, "assemblies": assemblies, "previews": previews}, ensure_ascii=False, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AssetsStudio Hair Component Variant Review</title>
  <style>
    :root { color-scheme: dark; font-family: ui-rounded, system-ui, sans-serif; background: #17151d; color: #f7eee8; }
    body { margin: 0; padding: 16px; background: radial-gradient(circle at top, #493329, #17151d 62%); }
    main { max-width: 1120px; margin: auto; }
    h1 { margin: 0 0 5px; font-size: clamp(1.45rem, 6vw, 2.35rem); }
    h2 { margin: 0 0 8px; font-size: 1.05rem; }
    .lead, .hint, footer { color: #d5b9ad; line-height: 1.45; font-size: .84rem; }
    .panel { border: 1px solid #765247; border-radius: 14px; background: #2a2024ee; box-shadow: 0 8px 24px #0006; padding: 13px; margin-bottom: 12px; }
    .workspace { display: grid; grid-template-columns: minmax(280px, 330px) minmax(0, 1fr); gap: 12px; align-items: start; }
    .controls { display: grid; gap: 9px; }
    label { color: #d5b9ad; font-size: .82rem; }
    select, input, button { box-sizing: border-box; width: 100%; border: 1px solid #765247; border-radius: 9px; padding: 8px 10px; background: #201a21; color: #f7eee8; font: inherit; }
    button { cursor: pointer; } button.primary { background: #b86649; border-color: #e59a73; color: #fff4ec; }
    .button-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .status { color: #f0c2a5; min-height: 1.25em; font-size: .8rem; }
    .reference { display: grid; gap: 6px; padding: 10px; border: 1px solid #5d4140; border-radius: 10px; }
    .reference strong { color: #ffc7a3; word-break: break-word; }
    .reference-preview { width: 100%; max-height: 180px; object-fit: contain; image-rendering: pixelated; background: #151219; border-radius: 7px; }
    .variant-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(245px, 1fr)); gap: 10px; }
    .variant { border: 1px solid #5d4140; border-radius: 10px; padding: 9px; background: #201a21; }
    .variant h3 { margin: 0 0 5px; font-size: .86rem; word-break: break-word; }
    .views { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px; }
    figure { min-width: 0; margin: 0; color: #d5b9ad; text-align: center; font-size: .68rem; }
    figure img { display: block; width: 100%; aspect-ratio: 1; object-fit: contain; image-rendering: pixelated; background: #151219; border-radius: 6px; }
    .meta { color: #d5b9ad; font-size: .74rem; word-break: break-word; line-height: 1.35; margin: 7px 0 0; }
    .actions { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 8px; }
    .actions button { width: auto; padding: 5px 7px; font-size: .72rem; }
    .score { color: #ffd19f; font-weight: 600; }
    .match-list { color: #d5b9ad; font-size: .72rem; line-height: 1.35; word-break: break-word; }
    .viewer { min-height: 320px; width: 100%; background: #151219; border-radius: 10px; }
    a { color: #ffc7a3; }
    .hidden { display: none !important; }
    @media (max-width: 820px) { body { padding: 10px; } .workspace { grid-template-columns: minmax(0, 1fr); } .variant-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 480px) { .variant-grid { grid-template-columns: minmax(0, 1fr); } .views { gap: 3px; } }
  </style>
</head>
<body><main>
  <script type="module" src="https://unpkg.com/@google/model-viewer@3.5.0/dist/model-viewer.min.js"></script>
  <h1>AssetsStudio 单部件变体工作台</h1>
  <p class="lead">这里的“随机”只作用于一个参考部件：使用共享部件池中的对象作为种子，生成可复现的几何变体并单独评审。组合装配请返回组合工作台。</p>
  <div class="workspace">
    <section class="panel">
      <h2>参考部件</h2>
      <div class="controls">
        <label>性别<select id="gender"><option value="female">女性</option><option value="male">男性</option></select></label>
        <label>部件角色<select id="role"></select></label>
        <label>参考部件<select id="reference"></select></label>
        <div class="reference" id="reference-info"></div>
        <button type="button" id="generate-pool-previews">生成共享部件预览缓存</button>
        <label>变体 Seed<input id="seed" type="number" value="1001" step="1"></label>
        <label>变体强度<select id="strength"><option value="0.08">轻微 8%</option><option value="0.12" selected>标准 12%</option><option value="0.18">明显 18%</option></select></label>
        <div class="button-row"><button type="button" id="random-seed">随机 Seed</button><button type="button" class="primary" id="generate-variant">生成并预览</button><button type="button" id="download-request">导出请求</button></div>
        <h3>联合预览部件</h3>
        <div class="controls" id="assembly-slots"></div>
        <button type="button" class="primary" id="generate-assembly">生成联合预览</button>
        <p class="status" id="status"></p>
        <p class="hint">生成请求由页面导出；实际几何生成由 Blender 后台工具执行。正式随机池不会被直接改写。</p>
        <a href="../workbench/index.html">返回组合装配工作台</a>
      </div>
    </section>
    <section class="panel">
      <h2 id="results-title">单部件变体结果</h2>
      <div class="variant-grid" id="variants"></div>
      <h2 id="assemblies-title">联合预览结果</h2>
      <div class="variant-grid" id="assemblies"></div>
      <h2>整体 3D 预览</h2>
      <model-viewer id="model-viewer" class="viewer" camera-controls touch-action="pan-y" shadow-intensity="0.25" exposure="1.1" interaction-prompt="none"></model-viewer>
      <p class="hint" id="model-note">选择联合预览卡片中的“加载 3D 模型”后，可在手机上拖动旋转和缩放；模型不可编辑。</p>
    </section>
  </div>
  <footer>参考来源：hair_random_pool_v1.json；结果来源：assetslab_hair_component_variant_v1 manifest。</footer>
</main>
<script>
const DATA = __DATA__;
const REVIEW_KEY = 'assetslab_hair_component_variant_reviews_v1';
const byId = (id) => document.getElementById(id);
let selectedGender = 'female';
let selectedRole = '';
let selectedReference = '';
let selectedVariantId = '';
const ASSEMBLY_ROLES = ['base_cap', 'front_bangs', 'side_coverage', 'back_section', 'back_attachment'];
let assemblyState = {};
const genders = { female: '女性', male: '男性' };
const roles = { base_cap: 'Base', front_bangs: '前发 / 刘海', side_coverage: '侧发', back_section: '后脑发段', back_attachment: '后部附件' };
function poolComponents() { return DATA.components.filter((item) => item.gender === selectedGender && item.pool && !item.preset); }
function roleOptions() { return [...new Set(poolComponents().map((item) => item.role))]; }
function refreshRoles() {
  const select = byId('role');
  const options = roleOptions();
  if (!options.includes(selectedRole)) selectedRole = options[0] || '';
  select.innerHTML = options.map((role) => `<option value="${role}">${roles[role] || role}</option>`).join('');
  select.value = selectedRole;
}
function refreshReferences() {
  const options = poolComponents().filter((item) => item.role === selectedRole);
  if (!options.some((item) => item.object === selectedReference)) selectedReference = options[0]?.object || '';
  byId('reference').innerHTML = options.map((item) => `<option value="${item.object}">${item.object}</option>`).join('');
  byId('reference').value = selectedReference;
  const reference = options.find((item) => item.object === selectedReference);
  const preview = DATA.previews.find((item) => item.source_object === selectedReference);
  byId('reference-info').innerHTML = reference ? `${preview ? `<img class="reference-preview" src="${preview.front}" alt="${reference.object} 预览">` : ''}<strong>${reference.object}</strong><span>共享池角色：${roles[reference.role] || reference.role}</span><span>来源：${reference.source_blend || '未登记'}</span><span>这是一个参考部件，不会自动拼接其它槽位。</span>` : '<span>当前角色没有可用参考部件。</span>';
  if (preview) {
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.textContent = '删除部件预览缓存';
    deleteButton.addEventListener('click', () => deletePreview(preview.id, '部件'));
    byId('reference-info').append(deleteButton);
  }
}
function assemblyOptions(role) { return DATA.components.filter((item) => item.gender === selectedGender && item.role === role && item.pool && !item.preset); }
function refreshAssemblySlots() {
  const container = byId('assembly-slots');
  if (!container) return;
  container.innerHTML = '';
  for (const role of ASSEMBLY_ROLES) {
    if (role === selectedRole) continue;
    const options = assemblyOptions(role);
    if (!options.length) continue;
    if (!(role in assemblyState) || !options.some((item) => item.component_id === assemblyState[role])) assemblyState[role] = role === 'base_cap' ? options[0].component_id : '';
    const label = document.createElement('label'); label.textContent = `${roles[role] || role}（可选）`;
    const select = document.createElement('select'); select.dataset.assemblyRole = role;
    select.innerHTML = `<option value="">不加入</option>` + options.map((item) => `<option value="${item.component_id}">${item.object}</option>`).join('');
    select.value = assemblyState[role]; select.addEventListener('change', (event) => { assemblyState[role] = event.target.value; });
    label.append(select); container.append(label);
  }
}
function selectedVariant() { return DATA.variants.find((item) => item.id === selectedVariantId) || DATA.variants.find((item) => item.source_object === selectedReference); }
function renderVariants() {
  const reviews = reviewRecords();
  const matches = DATA.variants.filter((item) => item.source_object === selectedReference && reviews[item.id]?.status !== 'discarded');
  byId('results-title').textContent = `${selectedReference || '未选择参考部件'} · 单部件变体（${matches.length}）`;
  const list = byId('variants'); list.innerHTML = '';
  if (!matches.length) { list.innerHTML = '<p class="hint">当前参考部件还没有生成变体。导出请求后由 Blender 后台生成，再重新构建本页。</p>'; return; }
  for (const variant of matches) {
    const card = document.createElement('article'); card.className = 'variant';
    const compatibility = variant.compatibility;
    const scoreLabel = document.createElement('p'); scoreLabel.className = 'score'; scoreLabel.textContent = compatibility ? `可用度：${compatibility.overall_score}/100` : '尚未评估可用度';
    const matchLabel = document.createElement('p'); matchLabel.className = 'match-list'; matchLabel.textContent = compatibility ? `推荐配合：${Object.entries(compatibility.best_matches || {}).map(([role, items]) => `${roles[role] || role}=${items[0]?.object || '无'}`).join('；')}` : '评估后显示各位置最佳匹配部件。';
    card.innerHTML = `<h3>Seed ${variant.variant_seed} · ${variant.id}</h3><div class="views"><figure><img src="${variant.front}" alt="正面"><figcaption>正面</figcaption></figure><figure><img src="${variant.right}" alt="右侧"><figcaption>右侧</figcaption></figure><figure><img src="${variant.back}" alt="背面"><figcaption>背面</figcaption></figure><figure><img src="${variant.left}" alt="左侧"><figcaption>左侧</figcaption></figure></div><p class="meta">强度 ${Number(variant.variant.strength || 0).toFixed(2)} · 宽 ${Number(variant.variant.width_scale || 1).toFixed(3)} · 深 ${Number(variant.variant.depth_scale || 1).toFixed(3)} · 高 ${Number(variant.variant.height_scale || 1).toFixed(3)}</p><div class="actions"><button type="button" data-select-variant="${encodeURIComponent(variant.id)}">${selectedVariantId === variant.id ? '已选作联合预览' : '选择联合预览'}</button><button type="button" data-accept="${encodeURIComponent(variant.id)}">加入本机候选</button><button type="button" data-discard="${encodeURIComponent(variant.id)}">销毁候选</button><span class="status">${reviews[variant.id]?.status === 'accepted_candidate' ? '已加入本机候选' : ''}</span></div>`;
    if (variant.blend) { const link = document.createElement('a'); link.href = variant.blend; link.target = '_blank'; link.textContent = '打开候选 Blend'; card.append(link); }
    card.prepend(matchLabel, scoreLabel);
    const scoreButton = document.createElement('button'); scoreButton.type = 'button'; scoreButton.textContent = '评估匹配度'; scoreButton.addEventListener('click', () => scoreVariant(variant)); card.querySelector('.actions')?.prepend(scoreButton);
    const deleteButton = document.createElement('button'); deleteButton.type = 'button'; deleteButton.textContent = '删除预览缓存'; deleteButton.addEventListener('click', () => deletePreview(variant.id, '单部件')); card.querySelector('.actions')?.append(deleteButton);
    list.append(card);
    card.querySelector('[data-accept]')?.addEventListener('click', () => saveReview(variant, 'accepted_candidate'));
    card.querySelector('[data-discard]')?.addEventListener('click', () => saveReview(variant, 'discarded'));
    card.querySelector('[data-select-variant]')?.addEventListener('click', () => { selectedVariantId = variant.id; renderVariants(); renderAssemblies(); });
  }
}
async function deletePreview(previewId, label) {
  if (!confirm(`确认删除${label}预览缓存？这不会删除源 Blend 或正式随机池。`)) return;
  byId('status').textContent = '正在删除预览缓存…';
  try {
    const response = await fetch('/api/delete-hair-preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ schema: 'assetslab_hair_preview_delete_request_v1', preview_id: previewId }) });
    const result = await response.json();
    if (!response.ok || !result.deleted) throw new Error(result.error || '删除失败');
    byId('status').textContent = `已删除：${(result.removed || []).join('、')}`;
    window.location.reload();
  } catch (error) { byId('status').textContent = `删除失败：${error.message}`; }
}
async function scoreVariant(variant) {
  byId('status').textContent = '正在计算部件可用度和各位置最佳匹配，请稍候…';
  try { const response = await fetch('/api/score-hair-component', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ schema: 'assetslab_hair_component_score_request_v1', variant_id: variant.id }) }); const result = await response.json(); if (!response.ok || !result.scored) throw new Error(result.error || '评分失败'); byId('status').textContent = `评分完成：${result.score.overall_score}/100，正在刷新…`; window.location.reload(); } catch (error) { byId('status').textContent = `评分失败：${error.message}`; }
}
function renderAssemblies() {
  const list = byId('assemblies'); list.innerHTML = '';
  const matches = DATA.assemblies.filter((item) => !selectedVariantId || item.variant_id === selectedVariantId);
  byId('assemblies-title').textContent = `联合预览结果（${matches.length}）`;
  if (!matches.length) { list.innerHTML = '<p class="hint">选择一个单部件变体并生成联合预览后，结果会显示在这里。</p>'; return; }
  for (const assembly of matches) {
    const card = document.createElement('article'); card.className = 'variant';
    card.innerHTML = `<h3>${assembly.id}</h3><div class="views"><figure><img src="${assembly.front}" alt="正面"><figcaption>正面</figcaption></figure><figure><img src="${assembly.right}" alt="右侧"><figcaption>右侧</figcaption></figure><figure><img src="${assembly.back}" alt="背面"><figcaption>背面</figcaption></figure><figure><img src="${assembly.left}" alt="左侧"><figcaption>左侧</figcaption></figure></div><p class="meta">部件：${(assembly.components || []).join(' / ')}</p>${assembly.model ? '<button type="button" data-load-model>加载 3D 模型</button>' : '<p class="hint">暂无 GLB 模型缓存</p>'}`;
    if (assembly.blend) { const link = document.createElement('a'); link.href = assembly.blend; link.target = '_blank'; link.textContent = '打开联合候选 Blend'; card.append(link); }
    card.querySelector('[data-load-model]')?.addEventListener('click', () => { byId('model-viewer').src = assembly.model; byId('model-note').textContent = `已加载 ${assembly.id}；拖动模型可查看各个角度。`; });
    const deleteButton = document.createElement('button'); deleteButton.type = 'button'; deleteButton.textContent = '删除联合预览'; deleteButton.addEventListener('click', () => deletePreview(assembly.id, '联合')); card.append(deleteButton);
    list.append(card);
  }
}
function reviewRecords() { try { return JSON.parse(localStorage.getItem(REVIEW_KEY) || '{}'); } catch { return {}; } }
function saveReview(variant, status) {
  const records = reviewRecords();
  records[variant.id] = { schema: 'assetslab_hair_component_variant_review_v1', lifecycle: status === 'accepted_candidate' ? 'pool_candidate' : 'discarded', status, variant_id: variant.id, source_object: variant.source_object, variant_seed: variant.variant_seed, reviewed_at: new Date().toISOString() };
  localStorage.setItem(REVIEW_KEY, JSON.stringify(records));
  byId('status').textContent = status === 'accepted_candidate' ? `已加入本机部件候选：${variant.id}` : `已销毁本机候选记录：${variant.id}（未删除源文件）`;
  renderVariants();
}
function refresh() { refreshRoles(); refreshReferences(); refreshAssemblySlots(); renderVariants(); renderAssemblies(); }
byId('gender').addEventListener('change', (event) => { selectedGender = event.target.value; selectedRole = ''; selectedReference = ''; refresh(); });
byId('role').addEventListener('change', (event) => { selectedRole = event.target.value; selectedReference = ''; selectedVariantId = ''; refreshReferences(); refreshAssemblySlots(); renderVariants(); renderAssemblies(); });
byId('reference').addEventListener('change', (event) => { selectedReference = event.target.value; selectedVariantId = ''; refreshReferences(); refreshAssemblySlots(); renderVariants(); renderAssemblies(); });
function currentRequest() {
  if (!selectedReference) { byId('status').textContent = '请先选择参考部件。'; return; }
  const reference = DATA.components.find((item) => item.object === selectedReference);
  return { schema: 'assetslab_hair_component_variant_request_v1', lifecycle: 'draft', gender: selectedGender, role: selectedRole, reference_component_id: reference.component_id, source_blend: reference.source_blend, hair_object: reference.object, source_anchor_object: selectedGender === 'female' ? 'Chloe_head_dummy' : 'Colin_head_dummy', variant_seed: Number(byId('seed').value), variant_strength: Number(byId('strength').value), created_at: new Date().toISOString() };
}
byId('random-seed').addEventListener('click', () => { byId('seed').value = Math.floor(Math.random() * 2147483647); byId('status').textContent = '已生成新的可复现 Seed，可直接生成预览。'; });
byId('generate-variant').addEventListener('click', async () => {
  const request = currentRequest();
  if (!request) return;
  const button = byId('generate-variant'); button.disabled = true; byId('status').textContent = 'Blender 正在后台生成单部件变体，请稍候…';
  try {
    const response = await fetch('/api/generate-hair-component-variant', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) });
    const result = await response.json();
    if (!response.ok || !result.generated) throw new Error(result.error || '生成失败');
    byId('status').textContent = result.cached ? '已命中已有候选，正在刷新预览…' : '生成完成，正在刷新预览…';
    window.location.href = result.page;
  } catch (error) {
    byId('status').textContent = `生成失败：${error.message}`;
    button.disabled = false;
  }
});
byId('generate-assembly').addEventListener('click', async () => {
  const variant = selectedVariant();
  if (!variant) { byId('status').textContent = '请先选择一个已生成的单部件变体。'; return; }
  const additional_component_ids = Object.values(assemblyState).filter(Boolean).filter((id) => id !== DATA.components.find((item) => item.object === variant.source_object)?.component_id);
  if (selectedRole !== 'base_cap' && !additional_component_ids.some((id) => DATA.components.find((item) => item.component_id === id)?.role === 'base_cap')) { byId('status').textContent = '联合预览需要加入 base。'; return; }
  const request = { schema: 'assetslab_hair_component_assembly_request_v1', variant_id: variant.id, additional_component_ids };
  const button = byId('generate-assembly'); button.disabled = true; byId('status').textContent = 'Blender 正在后台生成联合预览，请稍候…';
  try { const response = await fetch('/api/generate-hair-component-assembly', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) }); const result = await response.json(); if (!response.ok || !result.generated) throw new Error(result.error || '联合预览失败'); byId('status').textContent = '联合预览完成，正在刷新…'; window.location.href = result.page; } catch (error) { byId('status').textContent = `联合预览失败：${error.message}`; button.disabled = false; }
});
byId('generate-pool-previews').addEventListener('click', async () => {
  const button = byId('generate-pool-previews'); button.disabled = true; byId('status').textContent = '正在后台生成共享部件预览缓存，请稍候…';
  try { const response = await fetch('/api/generate-hair-pool-component-previews', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ schema: 'assetslab_hair_pool_component_preview_request_v1', gender: selectedGender }) }); const result = await response.json(); if (!response.ok || !result.generated) throw new Error(result.error || '部件预览缓存失败'); byId('status').textContent = `已缓存 ${result.generated_count} 个部件，正在刷新…`; window.location.href = result.page; } catch (error) { byId('status').textContent = `部件预览失败：${error.message}`; button.disabled = false; }
});
byId('download-request').addEventListener('click', () => {
  const request = currentRequest();
  if (!request) return;
  const blob = new Blob([JSON.stringify(request, null, 2)], { type: 'application/json' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `hair_component_variant_${selectedGender}_${selectedRole}_${request.variant_seed}.json`; link.click(); URL.revokeObjectURL(link.href); byId('status').textContent = '已导出单部件生成请求。';
});
refresh();
</script>
</body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace("__DATA__", data), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component-catalog", required=True, type=Path)
    parser.add_argument("--pool-catalog", required=True, type=Path)
    parser.add_argument("--variant-root", required=True, type=Path)
    parser.add_argument("--component-preview-root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    components = load_pool(args.pool_catalog.resolve(), args.component_catalog.resolve())
    variants = scan_variants(args.variant_root.resolve(), args.output.parent)
    assemblies = scan_assemblies(args.variant_root.resolve(), args.output.parent)
    previews = scan_component_previews(args.component_preview_root.resolve() if args.component_preview_root else None, args.output.parent)
    if not components:
        raise RuntimeError("shared hair pool is empty")
    build_page(args.output.resolve(), components, variants, assemblies, previews)
    print(f"HAIR_COMPONENT_PAGE_PASS components={len(components)} variants={len(variants)} assemblies={len(assemblies)} previews={len(previews)} output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
