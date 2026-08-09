import { CATEGORY_GLYPHS, STATUS_LABELS, type AssetCategory, type AssetRecord } from "../lib/registry";

interface AssetShelfProps {
  assets: AssetRecord[];
  activeCategory: AssetCategory;
  loadedCategories: Set<AssetCategory>;
  onSelect: (category: AssetCategory) => void;
}

export function AssetShelf({ assets, activeCategory, loadedCategories, onSelect }: AssetShelfProps) {
  return (
    <section className="asset-shelf" aria-label="资产静态图库">
      <div className="asset-shelf-heading">
        <div><p className="eyebrow">ASSET LIBRARY</p><h3>资产仓库</h3></div>
        <span>静态缓存 · 点击进入工作流</span>
      </div>
      <div className="asset-card-row">
        {assets.map((asset) => (
          <button
            type="button"
            className={`asset-card ${activeCategory === asset.category ? "selected" : ""}`}
            key={asset.id}
            onClick={() => onSelect(asset.category)}
          >
            <span className="asset-card-visual">
              {asset.thumbnail_url ? (
                <img src={asset.thumbnail_url} alt={`${asset.label}静态预览`} loading="lazy" />
              ) : (
                <span className={`asset-card-placeholder glyph-${asset.category}`}>
                  {CATEGORY_GLYPHS[asset.category]}
                </span>
              )}
              <small>{asset.thumbnail_url ? "已缓存" : "待生成"}</small>
            </span>
            <span className="asset-card-copy">
              <strong>{asset.label}</strong>
              <span>{loadedCategories.has(asset.category) ? "可交互" : STATUS_LABELS[asset.status]}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
