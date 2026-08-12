# IBR Canaã - Sistema Django

Sistema local de gestão e comunidade da Igreja Batista Regular Canaã, reconstruído integralmente em Python com Django.

## Tecnologias

- Python 3.14
- Django 6
- SQLite para desenvolvimento local
- Django Templates
- CSS próprio e responsivo
- Autenticação por sessão e proteção CSRF

Não há dependência de Astro, Node.js, React, Vite ou Tailwind.

## Preparação

No PowerShell:

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" manage.py migrate
& ".venv\Scripts\python.exe" manage.py seed_demo
```

## Executar

```powershell
& ".venv\Scripts\python.exe" manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

## Acessos locais

- Diretoria: `diretoria` / `Canaa@2026`
- Membro: `membro` / `Membro@2026`

Troque essas senhas antes de utilizar dados reais.

## Funcionalidades

- Landing page com formulário salvo no banco
- Login real com sessão Django
- Portal individual do membro
- Dashboard administrativo
- Cadastro e edição de membros
- Cadastro de eventos
- Lançamentos financeiros
- Relatórios consolidados
- Django Admin em `/django-admin/`

## Testes

```powershell
& ".venv\Scripts\python.exe" manage.py check
& ".venv\Scripts\python.exe" manage.py test
```

## Banco de produção

O ambiente local usa SQLite. Quando houver hospedagem, a configuração poderá ser alterada para PostgreSQL sem mudar os modelos ou templates.
