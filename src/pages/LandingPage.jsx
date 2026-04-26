import { Link } from 'react-router-dom';
import { Church, Users, HeartHandshake, Calendar as CalendarIcon, ArrowRight, PlayCircle } from 'lucide-react';
import Logo from '../components/common/Logo';
import Button from '../components/ui/Button';

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <header className="fixed top-0 w-full bg-white/80 backdrop-blur-md z-50 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          <Logo />
          <nav className="hidden md:flex gap-8 font-medium text-slate-600">
            <a href="#sobre" className="hover:text-blue-900 transition-colors">Sobre Nós</a>
            <a href="#ministerios" className="hover:text-blue-900 transition-colors">Ministérios</a>
            <a href="#agenda" className="hover:text-blue-900 transition-colors">Agenda</a>
          </nav>
          <div className="flex items-center gap-4">
            <Link to="/login">
              <Button variant="primary">Acessar Portal</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="pt-32 pb-20 lg:pt-48 lg:pb-32 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center max-w-3xl mx-auto">
          <h1 className="text-5xl lg:text-7xl font-extrabold text-slate-900 tracking-tight mb-8">
            Um Santuário Digital para uma <span className="text-blue-900">Fé Real</span>
          </h1>
          <p className="text-xl text-slate-500 mb-10 leading-relaxed">
            Bem-vindo ao Lumen Ecclesia, o portal digital da IBR Canaã. 
            Conecte-se com nossa comunidade, acompanhe eventos e cresça em sua jornada espiritual.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/login">
              <Button size="lg" className="w-full sm:w-auto gap-2">
                Comece sua Jornada <ArrowRight className="w-5 h-5" />
              </Button>
            </Link>
            <Button size="lg" variant="outline" className="w-full sm:w-auto gap-2">
              <PlayCircle className="w-5 h-5" /> Assistir Culto Online
            </Button>
          </div>
        </div>
      </section>

      {/* Sobre */}
      <section id="sobre" className="py-20 bg-white border-y border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl font-bold text-slate-900 mb-6">Ser Luz no Mundo</h2>
              <p className="text-lg text-slate-500 mb-8 leading-relaxed">
                Nossa missão é levar a esperança e o amor de Cristo para todos. 
                Através do Lumen Ecclesia, buscamos estar mais próximos de você, 
                oferecendo suporte espiritual, ensino de qualidade e uma comunidade acolhedora.
              </p>
              <div className="grid sm:grid-cols-2 gap-6">
                <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100">
                  <div className="w-12 h-12 bg-blue-100 text-blue-900 rounded-xl flex items-center justify-center mb-4">
                    <Users className="w-6 h-6" />
                  </div>
                  <h3 className="text-3xl font-bold text-slate-900 mb-1">+2.000</h3>
                  <p className="text-slate-500 font-medium">Membros Ativos</p>
                </div>
                <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100">
                  <div className="w-12 h-12 bg-blue-100 text-blue-900 rounded-xl flex items-center justify-center mb-4">
                    <Church className="w-6 h-6" />
                  </div>
                  <h3 className="text-3xl font-bold text-slate-900 mb-1">15</h3>
                  <p className="text-slate-500 font-medium">Ministérios</p>
                </div>
              </div>
            </div>
            <div className="relative">
              <div className="aspect-[4/3] rounded-3xl overflow-hidden shadow-2xl">
                <div className="absolute inset-0 bg-gradient-to-tr from-blue-900/20 to-transparent z-10" />
                <img 
                  src="https://images.unsplash.com/photo-1438232992991-995b7058bbb3?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80" 
                  alt="Comunidade na Igreja" 
                  className="w-full h-full object-cover"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Ministérios */}
      <section id="ministerios" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-slate-900 mb-4">Nossa Comunidade em Ação</h2>
          <p className="text-lg text-slate-500 mb-12 max-w-2xl mx-auto">Encontre seu lugar de servir e ser servido através dos nossos diversos ministérios.</p>
          
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { title: 'Louvor', desc: 'Adoração através da música.', icon: HeartHandshake },
              { title: 'Canaã Kids', desc: 'Semeando a palavra nos corações.', icon: Users },
              { title: 'Missões Globais', desc: 'Levando esperança além-fronteiras.', icon: Church }
            ].map((m, i) => (
              <div key={i} className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 text-left hover:shadow-md transition-shadow">
                <div className="w-14 h-14 bg-slate-50 text-blue-900 rounded-2xl flex items-center justify-center mb-6">
                  <m.icon className="w-7 h-7" />
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-2">{m.title}</h3>
                <p className="text-slate-500">{m.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agenda */}
      <section id="agenda" className="py-20 bg-slate-900 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold mb-12 text-center">Próximos Eventos</h2>
          <div className="grid gap-4 max-w-3xl mx-auto">
            {[
              { date: '24 Dez', title: 'Culto de Natal', desc: 'Celebração especial do nascimento de Cristo.' },
              { date: '31 Dez', title: 'Culto da Virada', desc: 'Agradecimento pelo ano e entrega do novo.' },
              { date: '15 Jan', title: 'Encontro de Liderança', desc: 'Treinamento para todos os líderes.' }
            ].map((e, i) => (
              <div key={i} className="bg-slate-800/50 backdrop-blur-sm p-6 rounded-2xl flex flex-col sm:flex-row sm:items-center gap-6 border border-slate-700/50 hover:bg-slate-800 transition-colors">
                <div className="bg-blue-900 text-white text-center py-3 px-6 rounded-xl shrink-0">
                  <span className="block font-bold text-xl">{e.date.split(' ')[0]}</span>
                  <span className="block text-xs uppercase tracking-wider">{e.date.split(' ')[1]}</span>
                </div>
                <div>
                  <h3 className="text-xl font-bold mb-1">{e.title}</h3>
                  <p className="text-slate-400">{e.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-12 text-center">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <Logo className="justify-center mb-6" />
          <p className="text-slate-500 mb-2">Av. Principal, 1000 - Centro</p>
          <p className="text-slate-500 mb-8">Cultos: Domingo 18h | Quarta 20h</p>
          <div className="pt-8 border-t border-slate-100 text-sm text-slate-400">
            © {new Date().getFullYear()} IBR Canaã / Lumen Ecclesia. Todos os direitos reservados.
          </div>
        </div>
      </footer>
    </div>
  );
}
