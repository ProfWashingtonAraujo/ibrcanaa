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

O ambiente local usa SQLite. Em produção no Render, o projeto usa PostgreSQL,
Gunicorn e WhiteNoise através do Blueprint `render.yaml`.

## Deploy no Render

1. Faça push da branch `main` para o GitHub.
2. No Render, escolha **New > Blueprint**.
3. Conecte o repositório `ProfWashingtonAraujo/ibrcanaa`.
4. Confirme os recursos definidos em `render.yaml`.
5. Aguarde o build, migrations e início do Gunicorn.

O serviço web e o banco PostgreSQL usam planos gratuitos. Como o serviço gratuito
não possui disco persistente, fotos enviadas pelos usuários podem ser perdidas
quando o Render reiniciar ou publicar uma nova versão. Para preservar uploads em
produção, será necessário usar armazenamento externo ou migrar para um plano com
disco persistente.

Depois do deploy, crie o primeiro administrador no Shell do Render:

```bash
python manage.py createsuperuser
```

## GitHub Pages

O GitHub Pages publica uma versão estática da página institucional em
`https://profwashingtonaraujo.github.io/ibrcanaa/`. Agenda, contato, login e
demais recursos dinâmicos direcionam para o serviço Django no Render. O workflow
`.github/workflows/deploy-pages.yml` executa os testes antes de cada publicação.
