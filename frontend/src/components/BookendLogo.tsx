// The Bookend logo (option H): a row of book spines in the palette, rising to a tall navy "bookend", beside
// the wordmark in a serif.

const SPINES: { color: string; h: number }[] = [
  { color: '#a49531', h: 0.56 }, // olive
  { color: '#a5c8d1', h: 0.66 }, // pale blue
  { color: '#8fa79f', h: 0.62 }, // sage (olive + pale blue)
  { color: '#bb7125', h: 0.74 }, // burnt orange
  { color: '#ffefae', h: 0.68 }, // cream
  { color: '#051230', h: 1.0 }, // navy: the bookend
]

export default function BookendLogo({ compact = false }: { compact?: boolean }) {
  return (
    <span className={compact ? 'logo-h compact' : 'logo-h'} aria-label="Bookend">
      <span className="spines-h" aria-hidden>
        {SPINES.map((s, i) => (
          <span key={i} style={{ background: s.color, height: `${s.h * 100}%` }} />
        ))}
      </span>
      <span className="wordmark">Bookend</span>
    </span>
  )
}
