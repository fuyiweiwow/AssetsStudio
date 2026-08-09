import { ASSET_CATEGORIES, CATEGORY_GLYPHS, STATUS_LABELS, type AssetRecord } from "../lib/registry";

interface AssetRailProps {
  assets: AssetRecord[];
  selectedId: string;
  onSelect: (asset: AssetRecord) => void;
}

export function AssetRail({ assets, selectedId, onSelect }: AssetRailProps) {
  const ordered = ASSET_CATEGORIES.map((category) =>
    assets.find((asset) => asset.category === category),
  ).filter((asset): asset is AssetRecord => Boolean(asset));

  return (
    <aside className="asset-rail" aria-label="当前资产里程碑">
      <div className="rail-heading">
        <span className="eyebrow">CURRENT LIBRARY</span>
        <h2>角色组件</h2>
        <span className="asset-count">{ordered.length} / 6</span>
      </div>
      <div className="asset-list">
        {ordered.map((asset) => (
          <button
            type="button"
            className={`asset-card ${selectedId === asset.id ? "selected" : ""}`}
            key={asset.id}
            onClick={() => onSelect(asset)}
          >
            <span className={`asset-glyph glyph-${asset.category}`} aria-hidden="true">
              {CATEGORY_GLYPHS[asset.category]}
            </span>
            <span className="asset-copy">
              <strong>{asset.label}</strong>
              <small>{asset.id}</small>
            </span>
            <span className={`status-chip status-${asset.status}`}>
              {STATUS_LABELS[asset.status]}
            </span>
          </button>
        ))}
      </div>
      <div className="rail-footnote">
        <span className="pulse-dot" />
        状态来自 ASSET_STATUS.json
      </div>
    </aside>
  );
}
