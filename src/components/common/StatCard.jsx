import { cn } from '../ui/Button';

export default function StatCard({ title, value, icon: Icon, trend, className }) {
  return (
    <div className={cn("bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-start gap-4", className)}>
      <div className="p-3 bg-blue-50 text-blue-900 rounded-xl">
        <Icon className="w-6 h-6" />
      </div>
      <div>
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <h3 className="text-2xl font-bold text-slate-900 mt-1">{value}</h3>
        {trend && (
          <p className={cn("text-sm mt-1 font-medium", trend.isPositive ? "text-emerald-600" : "text-red-600")}>
            {trend.isPositive ? '+' : '-'}{trend.value}% em relação ao mês anterior
          </p>
        )}
      </div>
    </div>
  );
}
