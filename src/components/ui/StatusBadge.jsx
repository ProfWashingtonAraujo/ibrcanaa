import { cn } from '../ui/Button';

export default function StatusBadge({ status, className }) {
  const styles = {
    'Ativo': 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
    'Visitante': 'bg-amber-50 text-amber-700 ring-amber-600/20',
    'Novo': 'bg-blue-50 text-blue-700 ring-blue-600/20',
    'Afastado': 'bg-red-50 text-red-700 ring-red-600/20',
    'Liderança': 'bg-purple-50 text-purple-700 ring-purple-600/20',
  };

  const defaultStyle = 'bg-slate-50 text-slate-700 ring-slate-600/20';

  return (
    <span className={cn("inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset", styles[status] || defaultStyle, className)}>
      {status}
    </span>
  );
}
