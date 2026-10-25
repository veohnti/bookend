import { useEffect, useMemo, useRef, useState } from 'react'
import { geoDistance, geoGraticule10, geoInterpolate, geoOrthographic, geoPath } from 'd3-geo'
import type { GeoPermissibleObjects } from 'd3-geo'
import { feature } from 'topojson-client'
import land110 from 'world-atlas/land-110m.json'

// A slowly turning globe with the continents and arcs flying between random cities: readers anywhere, talking
// about the same book. Land outlines: Natural Earth 1:110m (world-atlas), bundled with the app, no network needed.

const LAND = feature(land110 as any, (land110 as any).objects.land) as unknown as GeoPermissibleObjects
const GRATICULE = geoGraticule10()

// [longitude, latitude]
const CITIES: [number, number][] = [
  [-72.9, 41.3], [-74.0, 40.7], [-118.2, 34.1], [-99.1, 19.4], [-46.6, -23.5], [-58.4, -34.6], [-0.1, 51.5],
  [2.4, 48.9], [13.4, 52.5], [3.4, 6.5], [-0.2, 5.6], [36.8, -1.3], [31.2, 30.0], [18.4, -33.9], [37.6, 55.8],
  [77.2, 28.6], [72.9, 19.1], [103.8, 1.35], [139.7, 35.7], [127.0, 37.6], [151.2, -33.9], [174.8, -36.8],
  [-21.9, 64.1], [-79.4, 43.7], [55.3, 25.2], [121.0, 14.6],
]
const ARC_COLORS = ['#f48067', '#bb7125', '#ffefae', '#a49531']
const SIZE = 260
const ARC_LIFE = 5200 // ms: draw for 1.8s, hold, then fade
const DRAW = 1800

type Arc = { a: number; b: number; born: number; color: string }

export default function Globe({ size = 240 }: { size?: number }) {
  const [now, setNow] = useState(0)
  const start = useRef(performance.now())
  const arcs = useRef<Arc[]>([
    { a: 0, b: 6, born: -1500, color: ARC_COLORS[0] },
    { a: 9, b: 15, born: -600, color: ARC_COLORS[1] },
    { a: 18, b: 20, born: 0, color: ARC_COLORS[2] },
  ])

  useEffect(() => {
    let raf = 0
    let last = 0
    const tick = (t: number) => {
      if (t - last > 40) {
        const el = t - start.current
        arcs.current = arcs.current.filter((a) => el - a.born < ARC_LIFE)
        if (arcs.current.length < 5 && Math.random() < 0.09) {
          const a = Math.floor(Math.random() * CITIES.length)
          let b = Math.floor(Math.random() * CITIES.length)
          if (b === a) b = (b + 1) % CITIES.length
          arcs.current.push({ a, b, born: el, color: ARC_COLORS[Math.floor(Math.random() * ARC_COLORS.length)] })
        }
        setNow(el)
        last = t
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  const projection = useMemo(() => geoOrthographic().scale(SIZE / 2 - 14).translate([SIZE / 2, SIZE / 2]).clipAngle(90), [])
  const rotate: [number, number] = [-(((now / 1000) * 7 + 60) % 360), -18] // one turn about every 50 seconds
  projection.rotate(rotate)
  const path = geoPath(projection)
  const center: [number, number] = [-rotate[0], -rotate[1]]
  const visible = (p: [number, number]) => geoDistance(p, center) < Math.PI / 2 - 0.02
  const sphere = path({ type: 'Sphere' }) ?? ''

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={size} height={size} className="globe" role="img"
      aria-label="A globe with lines connecting readers in different cities">
      <defs>
        <radialGradient id="globe-sea" cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor="#1d3266" />
          <stop offset="70%" stopColor="#051230" />
          <stop offset="100%" stopColor="#020816" />
        </radialGradient>
        <radialGradient id="globe-glow" cx="50%" cy="50%" r="50%">
          <stop offset="82%" stopColor="#a5c8d1" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#a5c8d1" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="globe-shade" cx="35%" cy="30%" r="80%">
          <stop offset="55%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.45" />
        </radialGradient>
      </defs>
      <circle cx={SIZE / 2} cy={SIZE / 2} r={SIZE / 2 - 2} fill="url(#globe-glow)" />
      <path d={sphere} fill="url(#globe-sea)" />
      <path d={path(GRATICULE) ?? ''} fill="none" stroke="#a5c8d1" strokeOpacity={0.14} strokeWidth={0.6} />
      <path d={path(LAND) ?? ''} fill="#a5c8d1" fillOpacity={0.9} stroke="#d6e8ed" strokeOpacity={0.6} strokeWidth={0.4} />
      <path d={sphere} fill="url(#globe-shade)" />
      {CITIES.map((c, i) => {
        if (!visible(c)) return null
        const [x, y] = projection(c) ?? [0, 0]
        return <circle key={i} cx={x} cy={y} r={2.1} fill="#ffefae" stroke="#051230" strokeWidth={0.6} />
      })}
      {arcs.current.map((arc, i) => {
        const age = now - arc.born
        const drawn = Math.min(1, age / DRAW)
        const fade = age > ARC_LIFE - 1200 ? Math.max(0, (ARC_LIFE - age) / 1200) : 1
        const interp = geoInterpolate(CITIES[arc.a], CITIES[arc.b])
        const steps = 32
        const n = Math.max(1, Math.round(steps * drawn))
        const coords = Array.from({ length: n + 1 }, (_, s) => interp(s / steps))
        const head = coords[coords.length - 1] as [number, number]
        const hp = projection(head)
        return (
          <g key={`${arc.born}-${i}`} opacity={fade}>
            <path d={path({ type: 'LineString', coordinates: coords } as GeoPermissibleObjects) ?? ''} fill="none"
              stroke={arc.color} strokeWidth={2} strokeLinecap="round" />
            {drawn < 1 && hp && visible(head) && <circle cx={hp[0]} cy={hp[1]} r={3.2} fill={arc.color} />}
          </g>
        )
      })}
    </svg>
  )
}
