export default function Connector() {
  return (
    <div className="flex flex-col items-center py-1">
      <div className="w-px h-6 bg-slate-300"></div>
      <svg
        width="12"
        height="8"
        viewBox="0 0 12 8"
        fill="none"
        className="text-slate-400"
      >
        <path
          d="M1 1L6 7L11 1"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="w-px h-6 bg-slate-300"></div>
    </div>
  )
}
