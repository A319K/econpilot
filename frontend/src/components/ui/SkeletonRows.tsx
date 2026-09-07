export function SkeletonRows({ rows = 6, className = "" }: { rows?: number; className?: string }) {
  return (
    <div className={`flex flex-col gap-2 p-3 ${className}`} aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-(--color-bg-raised)"
          style={{ width: `${55 + ((i * 13) % 35)}%`, opacity: 0.6 }}
        />
      ))}
    </div>
  )
}
