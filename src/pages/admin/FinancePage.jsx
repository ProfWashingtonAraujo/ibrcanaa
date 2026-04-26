import { TrendingUp, TrendingDown, DollarSign, Plus, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import StatCard from '../../components/common/StatCard';
import Button from '../../components/ui/Button';
import { transactions, financeSummary } from '../../mocks/finance';

export default function FinancePage() {
  return (
    <div>
      <PageHeader 
        title="Gestão Financeira" 
        description="Acompanhe entradas, saídas e o saldo da congregação."
        action={
          <div className="flex gap-3">
            <Button variant="danger" className="gap-2">
              <ArrowDownRight className="w-4 h-4" /> Registrar Saída
            </Button>
            <Button className="gap-2 bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-600">
              <ArrowUpRight className="w-4 h-4" /> Registrar Entrada
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard 
          title="Saldo Atual" 
          value={`R$ ${financeSummary.balance.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`} 
          icon={DollarSign} 
        />
        <StatCard 
          title="Entradas (Mês)" 
          value={`R$ ${financeSummary.income.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`} 
          icon={TrendingUp} 
          className="border-emerald-100"
        />
        <StatCard 
          title="Saídas (Mês)" 
          value={`R$ ${financeSummary.expense.toLocaleString('pt-BR', {minimumFractionDigits: 2})}`} 
          icon={TrendingDown} 
          className="border-red-100"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <h3 className="text-lg font-bold text-slate-900 mb-6">Transações Recentes</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-sm font-medium text-slate-500">
                  <th className="pb-4 font-medium">Data</th>
                  <th className="pb-4 font-medium">Descrição</th>
                  <th className="pb-4 font-medium">Categoria</th>
                  <th className="pb-4 font-medium text-right">Valor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {transactions.map(tx => (
                  <tr key={tx.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="py-4 text-sm text-slate-500">
                      {new Date(tx.date).toLocaleDateString('pt-BR')}
                    </td>
                    <td className="py-4 font-medium text-slate-900">{tx.description}</td>
                    <td className="py-4 text-sm text-slate-600">{tx.category}</td>
                    <td className={`py-4 text-right font-bold ${tx.type === 'entrada' ? 'text-emerald-600' : 'text-red-600'}`}>
                      {tx.type === 'entrada' ? '+' : '-'} R$ {Math.abs(tx.amount).toLocaleString('pt-BR', {minimumFractionDigits: 2})}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-6 text-center">
            <Button variant="ghost">Ver todas as transações</Button>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <h3 className="text-lg font-bold text-slate-900 mb-6">Fluxo de Caixa (Anual)</h3>
          <div className="h-64 flex items-end justify-between gap-1 mt-4">
            {/* Gráfico Simulado */}
            {[4, 6, 5, 8, 5, 9, 7, 10, 6, 8, 12, 9].map((val, i) => (
              <div key={i} className="w-full relative group h-full flex items-end">
                <div 
                  className="w-full bg-blue-100 rounded-sm transition-all duration-300 group-hover:bg-blue-200"
                  style={{ height: `${val * 10}%` }}
                >
                  <div 
                    className="absolute bottom-0 w-full bg-emerald-500 rounded-sm opacity-80"
                    style={{ height: `${(val * 10) * 0.7}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-medium text-slate-400 uppercase tracking-wider">
            <span>J</span><span>F</span><span>M</span><span>A</span><span>M</span><span>J</span><span>J</span><span>A</span><span>S</span><span>O</span><span>N</span><span>D</span>
          </div>
          <div className="mt-6 flex items-center justify-center gap-4 text-sm">
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-emerald-500 rounded-sm"></div> Entradas</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 bg-blue-100 rounded-sm"></div> Saídas</div>
          </div>
        </div>
      </div>
    </div>
  );
}
