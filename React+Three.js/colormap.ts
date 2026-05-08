import * as THREE from 'three'

/**
 * Diverging color map for signed deviation:
 * Blue (inside CAD) ← White (on surface) → Red (outside CAD)
 */
export function deviationToColor(
  deviation_mm: number,
  scaleMin: number,
  scaleMax: number
): THREE.Color {
  // Clamp to scale bounds
  const clamped = Math.max(scaleMin, Math.min(scaleMax, deviation_mm))

  // Normalize to 0–1
  const t = (clamped - scaleMin) / (scaleMax - scaleMin)

  // Diverging blue → white → red
  if (t < 0.5) {
    // Blue to white
    const u = t * 2 // 0→1
    const r = u
    const g = u
    const b = 1.0
    return new THREE.Color(r, g, b)
  } else {
    // White to red
    const u = (t - 0.5) * 2 // 0→1
    const r = 1.0
    const g = 1.0 - u
    const b = 1.0 - u
    return new THREE.Color(r, g, b)
  }
}

/**
 * Viridis-like colormap for wall thickness (sequential, perceptually uniform).
 */
export function thicknessToColor(
  thickness_mm: number,
  minThickness: number,
  maxThickness: number
): THREE.Color {
  const t = Math.max(0, Math.min(1, (thickness_mm - minThickness) / (maxThickness - minThickness)))

  // Viridis approximation (purple → blue → green → yellow)
  const viridis = [
    [0.267004, 0.004874, 0.329415],
    [0.282623, 0.140926, 0.457517],
    [0.253935, 0.265254, 0.529983],
    [0.206756, 0.371758, 0.553117],
    [0.163625, 0.471133, 0.558148],
    [0.127568, 0.566949, 0.550556],
    [0.134692, 0.658636, 0.517649],
    [0.266941, 0.748751, 0.440573],
    [0.477504, 0.821444, 0.318195],
    [0.741388, 0.873449, 0.149561],
    [0.993248, 0.906157, 0.143936],
  ]

  const idx = t * (viridis.length - 1)
  const i0 = Math.floor(idx)
  const i1 = Math.min(i0 + 1, viridis.length - 1)
  const frac = idx - i0

  const c0 = viridis[i0]
  const c1 = viridis[i1]

  const r = c0[0] + (c1[0] - c0[0]) * frac
  const g = c0[1] + (c1[1] - c0[1]) * frac
  const b = c0[2] + (c1[2] - c0[2]) * frac

  return new THREE.Color(r, g, b)
}

/**
 * Format deviation value with sign and color coding for UI.
 */
export function formatDeviation(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(3)}`
}

/**
 * Get color class for deviation value (Tailwind).
 */
export function getDeviationColorClass(value: number): string {
  if (value < -0.1) return 'text-blue-400'
  if (value > 0.1) return 'text-red-400'
  return 'text-gray-300'
}
