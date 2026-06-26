import AppShell from '../../components/AppShell';
import Card from '../../components/Card';

export default function Settings() {
  return (
    <AppShell title="Settings">
      <Card title="Platform Settings">
        <p className="text-sm text-muted mb-4">Configure platform-wide settings below.</p>
        <div className="flex flex-col gap-4">
          {[['API Base URL', 'http://localhost:8000'], ['Gemini Model', 'gemini-2.0-flash'], ['Story Provider', 'gemini']].map(([label, value]) => (
            <div key={label}>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider mb-1.5">{label}</label>
              <input defaultValue={value} disabled
                className="w-full px-4 py-2.5 rounded-xl border border-greige-border bg-greige-accent text-muted text-sm cursor-not-allowed" />
            </div>
          ))}
        </div>
        <p className="text-xs text-muted mt-4">Settings are configured via <code className="bg-greige-accent px-1.5 py-0.5 rounded">.env</code> file on the server.</p>
      </Card>
    </AppShell>
  );
}
