import fs from 'node:fs'
import path from 'node:path'

const input = path.resolve('E:/WorkProject/AssetsStudio/milestones/robes/workflow_screening/patternsoft_mage_robe_v1/patternsoft_mage_robe_v1.patternsoft.json')
const output = path.resolve('E:/WorkProject/AssetsStudio/milestones/robes/workflow_screening/patternsoft_mage_robe_v2/patternsoft_mage_robe_v2.patternsoft.json')

const point = (id, x, y, curve) => curve ? { id, x, y, curve } : { id, x, y }
const curve = (inX, inY, outX, outY) => ({ in: { x: inX, y: inY }, out: { x: outX, y: outY } })
const seam = (defaultMm = 10, color = '#6b4aa1') => ({
  closed: true,
  seamAllowanceMm: defaultMm,
  grainLineLocked: false,
  notches: [],
  darts: [],
  group: 'robe',
  layerId: 'layer-robe',
  appearance: { material: 'wool', color, texture: 'solid' },
})

const robePieces = [
  {
    ...seam(),
    id: 'robe-v2-front-left',
    name: 'Front left',
    points: [
      point('v2-fl-neck-center', 0, 40, curve(18, 8, 22, 0)),
      point('v2-fl-neck-shoulder', 82, 0, curve(60, 0, 78, 0)),
      point('v2-fl-shoulder', 180, 0),
      point('v2-fl-armhole', 230, 120, curve(205, 18, 236, 70)),
      point('v2-fl-side-hem', 260, 680),
      point('v2-fl-center-hem', 0, 680),
    ],
    grainLine: { from: { x: 110, y: 85 }, to: { x: 125, y: 620 } },
    notches: [{ id: 'v2-fl-arm-notch', pointId: 'v2-fl-armhole', t: 0.45, side: 'right', type: 'v', depthMm: 6 }],
  },
  {
    ...seam(),
    id: 'robe-v2-front-right',
    name: 'Front right',
    points: [
      point('v2-fr-neck-center', 340, 40, curve(358, 8, 362, 0)),
      point('v2-fr-neck-shoulder', 422, 0, curve(400, 0, 418, 0)),
      point('v2-fr-shoulder', 520, 0),
      point('v2-fr-armhole', 570, 120, curve(545, 18, 576, 70)),
      point('v2-fr-side-hem', 600, 680),
      point('v2-fr-center-hem', 340, 680),
    ],
    grainLine: { from: { x: 450, y: 85 }, to: { x: 465, y: 620 } },
    notches: [{ id: 'v2-fr-arm-notch', pointId: 'v2-fr-armhole', t: 0.45, side: 'left', type: 'v', depthMm: 6 }],
  },
  {
    ...seam(10, '#5c3f8d'),
    id: 'robe-v2-back',
    name: 'Back',
    points: [
      point('v2-bk-neck-left', 700, 50, curve(735, 18, 770, 0)),
      point('v2-bk-neck-center', 800, 0, curve(830, 0, 865, 18)),
      point('v2-bk-neck-right', 900, 50),
      point('v2-bk-shoulder-right', 980, 110, curve(950, 75, 972, 86)),
      point('v2-bk-armhole-right', 1020, 240, curve(1018, 155, 1012, 205)),
      point('v2-bk-hem-right', 1000, 680),
      point('v2-bk-hem-left', 600, 680),
      point('v2-bk-armhole-left', 580, 240, curve(588, 205, 582, 155)),
      point('v2-bk-shoulder-left', 620, 110),
    ],
    grainLine: { from: { x: 800, y: 80 }, to: { x: 800, y: 620 } },
    notches: [
      { id: 'v2-bk-arm-notch-r', pointId: 'v2-bk-armhole-right', t: 0.5, side: 'right', type: 'v', depthMm: 6 },
      { id: 'v2-bk-arm-notch-l', pointId: 'v2-bk-armhole-left', t: 0.5, side: 'left', type: 'v', depthMm: 6 },
    ],
  },
  {
    ...seam(),
    id: 'robe-v2-sleeve-left',
    name: 'Sleeve left',
    group: 'sleeves',
    points: [
      point('v2-sl-underarm-left', 1120, 100),
      point('v2-sl-cap-left', 1180, 30, curve(1195, 0, 1220, -12)),
      point('v2-sl-cap-apex', 1290, -20, curve(1250, -32, 1330, -32)),
      point('v2-sl-cap-right', 1400, 30, curve(1360, -12, 1415, 0)),
      point('v2-sl-cuff-right', 1480, 520),
      point('v2-sl-cuff-left', 1120, 520),
    ],
    grainLine: { from: { x: 1300, y: 55 }, to: { x: 1310, y: 480 } },
    notches: [{ id: 'v2-sl-cap-notch', pointId: 'v2-sl-cap-apex', t: 0.5, side: 'right', type: 'v', depthMm: 6 }],
  },
  {
    ...seam(),
    id: 'robe-v2-sleeve-right',
    name: 'Sleeve right',
    group: 'sleeves',
    points: [
      point('v2-sr-underarm-left', 1530, 100),
      point('v2-sr-cap-left', 1590, 30, curve(1605, 0, 1630, -12)),
      point('v2-sr-cap-apex', 1700, -20, curve(1660, -32, 1740, -32)),
      point('v2-sr-cap-right', 1810, 30, curve(1770, -12, 1825, 0)),
      point('v2-sr-cuff-right', 1890, 520),
      point('v2-sr-cuff-left', 1530, 520),
    ],
    grainLine: { from: { x: 1710, y: 55 }, to: { x: 1720, y: 480 } },
    notches: [{ id: 'v2-sr-cap-notch', pointId: 'v2-sr-cap-apex', t: 0.5, side: 'left', type: 'v', depthMm: 6 }],
  },
  {
    ...seam(8, '#4c3475'),
    id: 'robe-v2-hood-left',
    name: 'Hood left',
    group: 'hood',
    layerId: 'layer-hood',
    points: [
      point('v2-hl-neck-front', 1980, 300),
      point('v2-hl-neck-back', 1880, 300),
      point('v2-hl-back-head', 1880, 160),
      point('v2-hl-crown', 1940, 40, curve(1965, 5, 2010, 25)),
      point('v2-hl-face-top', 2070, 50, curve(2110, 80, 2130, 125)),
      point('v2-hl-face-bottom', 2150, 160, curve(2140, 220, 2110, 275)),
      point('v2-hl-neck-opening', 2110, 300),
    ],
    grainLine: { from: { x: 1990, y: 80 }, to: { x: 2020, y: 270 } },
    internalPaths: [[point('v2-hl-face-line-1', 2070, 50), point('v2-hl-face-line-2', 2150, 160)]],
    notches: [{ id: 'v2-hl-neck-notch', pointId: 'v2-hl-neck-back', t: 0.5, side: 'left', type: 'v', depthMm: 5 }],
  },
  {
    ...seam(8, '#4c3475'),
    id: 'robe-v2-hood-right',
    name: 'Hood right',
    group: 'hood',
    layerId: 'layer-hood',
    points: [
      point('v2-hr-neck-front', 2260, 300),
      point('v2-hr-neck-back', 2160, 300),
      point('v2-hr-back-head', 2160, 160),
      point('v2-hr-crown', 2220, 40, curve(2245, 5, 2290, 25)),
      point('v2-hr-face-top', 2350, 50, curve(2390, 80, 2410, 125)),
      point('v2-hr-face-bottom', 2430, 160, curve(2420, 220, 2390, 275)),
      point('v2-hr-neck-opening', 2390, 300),
    ],
    grainLine: { from: { x: 2270, y: 80 }, to: { x: 2300, y: 270 } },
    internalPaths: [[point('v2-hr-face-line-1', 2350, 50), point('v2-hr-face-line-2', 2430, 160)]],
    notches: [{ id: 'v2-hr-neck-notch', pointId: 'v2-hr-neck-back', t: 0.5, side: 'right', type: 'v', depthMm: 5 }],
  },
]

const sizes = ['S', 'M', 'L']
const deltas = { S: {}, L: {} }
for (const p of robePieces) {
  for (const pt of p.points) {
    if (pt.id.includes('hem') || pt.id.includes('cuff')) {
      deltas.S[pt.id] = { dx: 0, dy: -18 }
      deltas.L[pt.id] = { dx: 0, dy: 18 }
    }
  }
}

const record = {
  type: 'visual',
  name: 'Mage Robe v2 - Curved Pattern',
  description: 'Curved hooded robe paper pattern with armholes, sleeve caps, hood face opening, seam allowances, notches, and conservative S/M/L grading.',
  notes: 'This is a paper-pattern benchmark, not yet a 3D garment. Validate seam matching and actor fit in Blender before production use.',
  tags: ['mage', 'robe', 'hood', 'patternsoft', 'milestone-v2', 'curved-pattern'],
  sizes,
  thumbnailPath: null,
  projectPath: null,
  visual: {
    pieces: robePieces,
    grading: { baseSize: 'M', sizes, deltas, rules: [], bindings: {} },
    layers: [
      { id: 'layer-robe', name: 'Robe body and sleeves', visible: true, locked: false },
      { id: 'layer-hood', name: 'Hood', visible: true, locked: false },
    ],
    annotations: [
      { id: 'v2-note', kind: 'text', x: 20, y: 740, text: 'MAGE ROBE V2 | curved armholes + sleeve caps + two-piece hood | base M' },
    ],
    seams: [
      { id: 'v2-seam-fl-bk-left-neck', name: 'Front left neck shoulder', a: { pieceId: 'robe-v2-front-left', segmentIndex: 1 }, b: { pieceId: 'robe-v2-back', segmentIndex: 8 }, reversed: true },
      { id: 'v2-seam-fl-bk-left-arm', name: 'Front left shoulder to back', a: { pieceId: 'robe-v2-front-left', segmentIndex: 2 }, b: { pieceId: 'robe-v2-back', segmentIndex: 7 }, reversed: true },
      { id: 'v2-seam-fr-bk-right-neck', name: 'Front right neck shoulder', a: { pieceId: 'robe-v2-front-right', segmentIndex: 1 }, b: { pieceId: 'robe-v2-back', segmentIndex: 2 }, reversed: true },
      { id: 'v2-seam-fr-bk-right-arm', name: 'Front right shoulder to back', a: { pieceId: 'robe-v2-front-right', segmentIndex: 2 }, b: { pieceId: 'robe-v2-back', segmentIndex: 3 }, reversed: true },
      { id: 'v2-seam-fl-bk-side', name: 'Left robe side', a: { pieceId: 'robe-v2-front-left', segmentIndex: 3 }, b: { pieceId: 'robe-v2-back', segmentIndex: 4 }, reversed: true },
      { id: 'v2-seam-fr-bk-side', name: 'Right robe side', a: { pieceId: 'robe-v2-front-right', segmentIndex: 3 }, b: { pieceId: 'robe-v2-back', segmentIndex: 6 }, reversed: true },
      { id: 'v2-seam-fl-sl', name: 'Front left armhole to sleeve', a: { pieceId: 'robe-v2-front-left', segmentIndex: 2 }, b: { pieceId: 'robe-v2-sleeve-left', segmentIndex: 1 }, reversed: true },
      { id: 'v2-seam-fr-sr', name: 'Front right armhole to sleeve', a: { pieceId: 'robe-v2-front-right', segmentIndex: 2 }, b: { pieceId: 'robe-v2-sleeve-right', segmentIndex: 1 }, reversed: true },
      { id: 'v2-seam-hood-center', name: 'Hood center seam', a: { pieceId: 'robe-v2-hood-left', segmentIndex: 1 }, b: { pieceId: 'robe-v2-hood-right', segmentIndex: 1 }, reversed: true },
      { id: 'v2-seam-hood-neck', name: 'Hood neckline', a: { pieceId: 'robe-v2-hood-left', segmentIndex: 0 }, b: { pieceId: 'robe-v2-front-left', segmentIndex: 0 }, reversed: true },
    ],
    reviewStatus: 'draft',
    metadata: { name: 'Mage Robe v2 - Curved Pattern', description: 'First realistic paper-pattern benchmark before Blender cloth fitting.' },
  },
}

fs.mkdirSync(path.dirname(output), { recursive: true })
fs.writeFileSync(output, JSON.stringify({ version: 1, record }, null, 2), 'utf8')
console.log(output)
console.log(`pieces=${robePieces.length} sizes=${sizes.join(',')} seams=${record.visual.seams.length}`)
