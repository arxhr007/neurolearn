export default function Badge({ children, variant = 'default' }) {
  const cls = {
    default: 'bg-sage-soft text-sage-dark',
    clay: 'bg-clay-soft text-clay',
    muted: 'bg-greige-accent text-muted',
  }[variant] || 'bg-sage-soft text-sage-dark';
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}>
      {children}
    </span>
  );
}
