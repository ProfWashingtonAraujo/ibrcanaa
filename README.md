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

O ambiente local usa SQLite. Em produção, o projeto usa PostgreSQL no Neon e a
aplicação usa Gunicorn e WhiteNoise no Render através do Blueprint
`render.yaml`.

Render e Vercel devem receber a mesma *pooled connection string* do Neon na
variável `DATABASE_URL`. Mantenha `sslmode=require` na URL fornecida pelo Neon.

### Criar o banco no Neon

1. Crie um projeto no Neon e selecione uma região próxima da aplicação.
2. No painel do projeto, abra **Connect** e selecione **Pooled connection**.
3. Copie a URL PostgreSQL completa, incluindo `sslmode=require`.
4. No Render, defina essa URL em `DATABASE_URL` e faça um novo deploy.
5. Na Vercel, defina a mesma URL em `DATABASE_URL` para compartilhar os dados.

O comando `bash build.sh` aplica todas as migrations e cria automaticamente a
estrutura de tabelas no primeiro deploy. Para preservar dados do banco anterior,
importe um backup no Neon antes de liberar o novo banco para uso.

## Mídia de imagens

Os arquivos enviados no perfil do usuário usam `ImageField`.
Para evitar perda de mídia em ambientes sem disco persistente, defina
`CLOUDINARY_URL` e o Django passa a armazenar essas imagens no Cloudinary.
Sem essa variável, o projeto continua usando o armazenamento local no
desenvolvimento.

## Deploy no Render

1. Faça push da branch `main` para o GitHub.
2. No Render, escolha **New > Blueprint**.
3. Conecte o repositório `ProfWashingtonAraujo/ibrcanaa`.
4. Informe a *pooled connection string* do Neon quando o Blueprint solicitar
   `DATABASE_URL`.
5. Confirme os recursos definidos em `render.yaml`.
6. Aguarde o build, migrations e início do Gunicorn.

O serviço web usa o plano gratuito do Render e o PostgreSQL fica no Neon. Como o
serviço web não possui disco persistente, fotos enviadas pelos usuários podem ser
perdidas quando o Render reiniciar ou publicar uma nova versão. Para preservar
uploads em produção, configure `CLOUDINARY_URL`.

Depois do deploy, crie o primeiro administrador no Shell do Render:

```bash
python manage.py createsuperuser
```

## Deploy na Vercel

O projeto também pode ser publicado na Vercel como app Django.

1. Importe o repositório `ProfWashingtonAraujo/ibrcanaa` e mantenha o diretório
   raiz do projeto como `.`. A Vercel detectará `manage.py` e
   `config/wsgi.py`; não selecione `pages/` como diretório raiz, pois essa pasta
   contém somente a versão estática usada pelo GitHub Pages.
2. No painel do Neon, copie a **Pooled connection string**.
3. Defina `DATABASE_URL` na Vercel com essa URL para que os dois deploys
   compartilhem usuários, conteúdo e demais dados.
4. Defina `DJANGO_DEBUG=False`.
5. Configure `DJANGO_SECRET_KEY`.
6. Se quiser armazenar imagens, defina `CLOUDINARY_URL`.
7. Faça o deploy. O build aplica as migrations no PostgreSQL e a aplicação
   completa fica disponível, incluindo `/entrar/`, `/admin/` e
   `/django-admin/`.

Configure as variáveis para **Production, Preview e Development** caso queira
que todos os ambientes usem o Django com o banco compartilhado. Para evitar que
deploys de preview acessem os dados reais, configure-as somente em Production.

Para criar o primeiro usuário automaticamente no build, defina também:

- `DJANGO_BOOTSTRAP_USERNAME`
- `DJANGO_BOOTSTRAP_PASSWORD`
- `DJANGO_BOOTSTRAP_EMAIL` (opcional)
- `DJANGO_BOOTSTRAP_FIRST_NAME` (opcional)
- `DJANGO_BOOTSTRAP_LAST_NAME` (opcional)
- `DJANGO_BOOTSTRAP_ROLE` (opcional, padrão `board`)
- `DJANGO_BOOTSTRAP_IS_STAFF` (opcional, padrão `true`)
- `DJANGO_BOOTSTRAP_IS_SUPERUSER` (opcional, padrão `false`)

Variáveis importantes na Vercel:

- `DATABASE_URL`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `CLOUDINARY_URL`

O arquivo `vercel.json` aumenta o tempo máximo da função principal para 60s.

## GitHub Pages

O GitHub Pages publica uma versão estática da página institucional em
`https://profwashingtonaraujo.github.io/ibrcanaa/`. Agenda, contato, login e
demais recursos dinâmicos direcionam para o serviço Django no Render. O workflow
`.github/workflows/deploy-pages.yml` executa os testes antes de cada publicação.
