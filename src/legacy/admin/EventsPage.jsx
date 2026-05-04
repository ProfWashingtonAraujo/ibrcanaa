import { Plus, Calendar as CalendarIcon, MapPin, Users } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import { events } from '../../mocks/events';

export default function EventsPage() {
  return (
    <div>
      <PageHeader 
        title="Agenda e Eventos" 
        description="Organize os cultos, encontros e celebrações da igreja."
        action={
          <Button className="gap-2">
            <Plus className="w-4 h-4" /> Novo Evento
          </Button>
        }
      />

      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 mb-8">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Button variant="secondary" className="bg-slate-900 text-white hover:bg-slate-800">Próximos</Button>
          <Button variant="ghost">Anteriores</Button>
          <Button variant="ghost">Calendário Completo</Button>
        </div>

        {events.length > 0 ? (
          <div className="space-y-4">
            {events.map((event) => {
              const date = new Date(event.date);
              const month = date.toLocaleString('pt-BR', { month: 'short' }).toUpperCase();
              const day = date.getDate();
              const time = date.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit' });

              return (
                <div key={event.id} className="flex flex-col md:flex-row md:items-center gap-6 p-4 rounded-2xl border border-slate-100 hover:border-blue-200 hover:shadow-md transition-all group">
                  <div className="w-20 h-20 bg-blue-50 rounded-xl flex flex-col items-center justify-center shrink-0 border border-blue-100 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                    <span className="text-sm font-bold opacity-80">{month}</span>
                    <span className="text-2xl font-black">{day}</span>
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-600 rounded-md">
                        {event.type}
                      </span>
                    </div>
                    <h3 className="text-xl font-bold text-slate-900">{event.title}</h3>
                    
                    <div className="flex flex-wrap gap-4 mt-3 text-sm text-slate-500">
                      <div className="flex items-center gap-1.5">
                        <CalendarIcon className="w-4 h-4" /> {time}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-4 h-4" /> {event.location}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Users className="w-4 h-4" /> {event.attendees} pessoas esperadas
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button variant="outline">Editar</Button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState 
            title="Nenhum evento agendado" 
            description="Não há eventos futuros programados para os próximos dias."
            actionLabel="Criar Evento"
          />
        )}
      </div>
    </div>
  );
}
