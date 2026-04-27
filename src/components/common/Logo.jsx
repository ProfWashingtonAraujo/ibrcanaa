import logo from '../../assets/logo.png';
import { cn } from '../ui/Button';

export default function Logo({ className, iconOnly = false, size = "md" }) {
  const textSizes = {
    sm: { label: "text-[8px]", title: "text-base" },
    md: { label: "text-[10px]", title: "text-lg" },
    lg: { label: "text-[12px]", title: "text-xl" }
  };

  const currentSize = textSizes[size] || textSizes.md;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <img 
        src={logo} 
        alt="IBR Canaã" 
        className={cn(
          "w-auto object-contain transition-all duration-300 hover:brightness-110",
          size === "sm" ? "h-10" : size === "md" ? "h-12" : "h-14",
          iconOnly && (size === "sm" ? "h-8" : size === "md" ? "h-10" : "h-12")
        )}
      />
      {!iconOnly && (
        <div className="flex flex-col border-l-2 border-slate-100 pl-3 py-0.5">
          <span className={cn(
            "font-extrabold text-slate-400 tracking-[0.3em] uppercase",
            currentSize.label
          )}>
            Igreja
          </span>
          <span className={cn(
            "font-bold leading-none tracking-tight text-blue-900 whitespace-nowrap",
            currentSize.title
          )}>
            Batista Regular Canaã
          </span>
        </div>
      )}
    </div>
  );
}
