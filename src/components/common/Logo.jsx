import { Church } from 'lucide-react';
import { cn } from '../ui/Button';

export default function Logo({ className, iconOnly = false }) {
  return (
    <div className={cn("flex items-center gap-2 text-blue-900", className)}>
      <Church className="h-8 w-8" />
      {!iconOnly && (
        <div className="flex flex-col">
          <span className="font-bold text-lg leading-none tracking-tight">IBR Canaã</span>
          <span className="text-xs font-medium text-slate-500 tracking-wider">LUMEN ECCLESIA</span>
        </div>
      )}
    </div>
  );
}
