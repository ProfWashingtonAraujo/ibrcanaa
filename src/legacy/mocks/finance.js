export const transactions = [
  { id: 1, date: '2024-03-15', description: 'Dízimo - Membro Anônimo', category: 'Dízimos', type: 'entrada', amount: 500.00 },
  { id: 2, date: '2024-03-14', description: 'Conta de Luz', category: 'Manutenção', type: 'saida', amount: -350.00 },
  { id: 3, date: '2024-03-14', description: 'Oferta Culto de Domingo', category: 'Ofertas', type: 'entrada', amount: 1250.50 },
  { id: 4, date: '2024-03-12', description: 'Material Escola Bíblica', category: 'Materiais', type: 'saida', amount: -120.00 },
  { id: 5, date: '2024-03-10', description: 'Dízimo - João Silva', category: 'Dízimos', type: 'entrada', amount: 1000.00 },
  { id: 6, date: '2024-03-08', description: 'Ajuda Missionária - África', category: 'Missões', type: 'saida', amount: -800.00 },
];

export const financeSummary = {
  balance: 15450.00,
  income: 28500.00,
  expense: 13050.00,
  trend: { isPositive: true, value: 12.5 }
};
