export default function Card({ title, children, className = '', action }) {
  return (
    <div className={`bg-greige-panel rounded-2xl border border-greige-border shadow-card p-5 hover:shadow-lift hover:-translate-y-0.5 transition-all duration-200 ${className}`}>
      {title && (
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-ink m-0">{title}</h3>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function MetricCard({ label, value }) {
  return (
    <div className="bg-greige-panel rounded-2xl border border-greige-border shadow-card p-5 hover:shadow-lift hover:-translate-y-0.5 transition-all duration-200">
      <p className="text-xs uppercase tracking-widest text-muted font-medium m-0 mb-3">{label}</p>
      <p className="text-3xl font-bold text-sage m-0">{value ?? '—'}</p>
    </div>
  );
}
