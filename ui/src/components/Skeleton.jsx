export default function Skeleton({ lines = 3 }) {
  const widths = ['w-full', 'w-4/5', 'w-3/5', 'w-full', 'w-2/3', 'w-3/4']

  return (
    <div className="space-y-2.5 py-1">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={`h-3 rounded shimmer-bar ${widths[i % widths.length]}`}
        />
      ))}
    </div>
  )
}
