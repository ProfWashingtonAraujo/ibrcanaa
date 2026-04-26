import PageHeader from '../../components/common/PageHeader';
import Button from '../../components/ui/Button';

export default function SettingsPage() {
  return (
    <div>
      <PageHeader 
        title="Configurações" 
        description="Gerencie as configurações da plataforma e informações da instituição."
        action={
          <Button>Salvar Alterações</Button>
        }
      />

      <div className="grid lg:grid-cols-4 gap-8">
        <div className="lg:col-span-1">
          <nav className="flex flex-col gap-1">
            <button className="text-left px-4 py-2.5 rounded-xl bg-blue-50 text-blue-900 font-medium">Perfil da Igreja</button>
            <button className="text-left px-4 py-2.5 rounded-xl text-slate-600 hover:bg-slate-50 font-medium">Usuários e Permissões</button>
            <button className="text-left px-4 py-2.5 rounded-xl text-slate-600 hover:bg-slate-50 font-medium">Integrações</button>
            <button className="text-left px-4 py-2.5 rounded-xl text-slate-600 hover:bg-slate-50 font-medium">Assinatura</button>
          </nav>
        </div>

        <div className="lg:col-span-3 space-y-6">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Informações Básicas</h3>
            <div className="grid sm:grid-cols-2 gap-6">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Nome da Instituição</label>
                <input type="text" defaultValue="IBR Canaã / Lumen Ecclesia" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">CNPJ</label>
                <input type="text" defaultValue="00.000.000/0001-00" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Telefone Principal</label>
                <input type="text" defaultValue="(11) 9999-9999" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-4">Endereço Principal</h3>
            <div className="grid sm:grid-cols-2 gap-6">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-slate-700 mb-1">Logradouro</label>
                <input type="text" defaultValue="Av. Principal, 1000" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Bairro</label>
                <input type="text" defaultValue="Centro" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Cidade / Estado</label>
                <input type="text" defaultValue="São Paulo / SP" className="w-full px-3 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
