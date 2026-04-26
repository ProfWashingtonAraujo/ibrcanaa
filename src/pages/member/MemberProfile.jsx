import { Camera, MapPin, Mail, Phone, Calendar, Shield } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import Button from '../../components/ui/Button';

export default function MemberProfile() {
  return (
    <div>
      <PageHeader title="Meu Perfil" description="Gerencie suas informações pessoais e preferências." />

      <div className="grid lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <div className="bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden mb-8">
            <div className="h-32 bg-gradient-to-r from-blue-900 to-blue-700 relative">
              <button className="absolute bottom-4 right-4 p-2 bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white rounded-lg transition-colors">
                <Camera className="w-4 h-4" />
              </button>
            </div>
            <div className="px-6 sm:px-8 pb-8">
              <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-end -mt-12 mb-8">
                <div className="relative">
                  <img src="https://i.pravatar.cc/150?u=1" alt="Perfil" className="w-24 h-24 sm:w-32 sm:h-32 rounded-2xl border-4 border-white shadow-sm bg-slate-200" />
                  <button className="absolute bottom-2 right-2 p-1.5 bg-blue-900 text-white rounded-lg hover:bg-blue-800 transition-colors shadow-sm">
                    <Camera className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-slate-900">João Silva</h2>
                  <p className="text-slate-500">Membro desde 2022 • Ministério de Louvor</p>
                </div>
                <Button>Editar Perfil</Button>
              </div>

              <div className="grid sm:grid-cols-2 gap-8">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">Informações de Contato</h3>
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 text-slate-600">
                      <Mail className="w-5 h-5 text-slate-400" />
                      <span>joao.silva@email.com</span>
                    </div>
                    <div className="flex items-center gap-3 text-slate-600">
                      <Phone className="w-5 h-5 text-slate-400" />
                      <span>(11) 98765-4321</span>
                    </div>
                    <div className="flex items-center gap-3 text-slate-600">
                      <MapPin className="w-5 h-5 text-slate-400" />
                      <span>São Paulo, SP</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">Informações Pessoais</h3>
                  <div className="space-y-4">
                    <div className="flex items-center gap-3 text-slate-600">
                      <Calendar className="w-5 h-5 text-slate-400" />
                      <span>Nascido em 15/05/1990</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-8">
          <div className="bg-blue-900 rounded-3xl p-6 text-white text-center shadow-lg shadow-blue-900/20">
            <h3 className="text-lg font-bold mb-2">Check-in Rápido</h3>
            <p className="text-blue-200 text-sm mb-6">Apresente este código nos cultos e eventos.</p>
            
            <div className="bg-white p-4 rounded-2xl mx-auto w-48 h-48 flex items-center justify-center mb-4">
              <div className="grid grid-cols-4 grid-rows-4 gap-1 w-full h-full">
                {/* SVG Mock QR Code pattern */}
                {[...Array(16)].map((_, i) => (
                  <div key={i} className={`bg-slate-900 rounded-sm ${i % 3 === 0 || i % 5 === 0 ? 'opacity-100' : 'opacity-0'}`}></div>
                ))}
                <div className="absolute inset-0 m-auto w-16 h-16 border-4 border-slate-900 rounded-lg"></div>
              </div>
            </div>
            <p className="font-mono text-blue-200 tracking-widest text-sm">ID: 8492-3310</p>
          </div>

          <div className="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-600" /> Segurança
            </h3>
            <div className="space-y-4">
              <Button variant="outline" className="w-full justify-start text-left">Alterar Senha</Button>
              <Button variant="outline" className="w-full justify-start text-left">Autenticação em 2 Fatores</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
