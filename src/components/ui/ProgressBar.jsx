import { cn } from './Button';

export default function ProgressBar({ value, max = 100, className, colorClass = "bg-blue-600" }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  return (
    <div className={cn("w-full bg-slate-100 rounded-full h-2 overflow-hidden", className)}>
      <div 
        className={cn("h-2 rounded-full transition-all duration-500", colorClass)} 
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
