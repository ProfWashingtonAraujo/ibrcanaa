import { SearchX } from 'lucide-react';
import Button, { cn } from './Button';

export default function EmptyState({ title, description, actionLabel, onAction, className }) {
  return (
    <div className={cn("flex flex-col items-center justify-center p-12 text-center border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50", className)}>
      <div className="p-4 bg-white rounded-full shadow-sm mb-4">
        <SearchX className="w-8 h-8 text-slate-400" />
      </div>
      <h3 className="text-lg font-medium text-slate-900 mb-1">{title}</h3>
      <p className="text-slate-500 mb-6 max-w-sm">{description}</p>
      {actionLabel && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
