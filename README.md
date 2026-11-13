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

Por segurança, `DJANGO_DEBUG` assume `False`. Só o valor `true` (sem distinguir maiúsculas) liga o debug; `1` ou `yes` contam como `False`. Para desenvolvimento local e para rodar os testes defina `DJANGO_DEBUG=True` (`$env:DJANGO_DEBUG="True"` no PowerShell; `export DJANGO_DEBUG=True` no Linux/macOS), por exemplo `DJANGO_DEBUG=True python manage.py test`. Fora do modo debug, `DJANGO_SECRET_KEY` (valor único, nunca o placeholder nem `django-insecure-...`) e `DATABASE_URL` são obrigatórias, e `seed_demo` é bloqueado.

**Vercel e Render:** `DJANGO_SECRET_KEY` e `DATABASE_URL` precisam existir em todos os ambientes que executam o build (Production **e Preview** na Vercel). Sem elas o `build.sh` falha na importação do settings. No Render o `render.yaml` já gera a chave.

**Proteção do login e do contato:** o login usa `django-axes`: após 5 falhas seguidas para o mesmo usuário e IP, o acesso fica bloqueado por 15 minutos (resposta 429), e o contador zera após um login bem-sucedido. As tentativas ficam no banco, então valem entre instâncias; `migrate` cria as tabelas. O IP do cliente vem de `x-vercel-forwarded-for` só quando o app roda na Vercel (a plataforma sobrescreve esse cabeçalho); nos demais ambientes usa-se `REMOTE_ADDR`, e `X-Forwarded-For` nunca é lido. O formulário de contato tem um campo isca (honeypot): envios com ele preenchido são descartados sem aviso. Para liberar um usuário bloqueado antes do prazo, use `python manage.py axes_reset_username <usuario>`.

**Hosts e CSRF:** não há curingas como `*.vercel.app`. O app confia apenas nos hosts que a própria plataforma informa (`VERCEL_URL`, `VERCEL_BRANCH_URL`, `VERCEL_PROJECT_PRODUCTION_URL` e `RENDER_EXTERNAL_HOSTNAME`). Para domínio próprio ou outro alias, defina `DJANGO_ALLOWED_HOSTS` (hosts separados por vírgula) e `DJANGO_CSRF_TRUSTED_ORIGINS` (origens com `https://`).

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

## YouTube ao vivo na home

A seção "Transmissões mais recentes" funciona assim:

| Situação | Destaque grande | Pilha lateral |
|---|---|---|
| Nada ao vivo | Vídeo fixo da igreja | 3 transmissões mais recentes |
| Ao vivo | A live, com o selo "Ao vivo agora" | 3 transmissões mais recentes |
| Live termina | Volta ao vídeo fixo | A live encerrada vira o 1º da pilha |

- **Fontes:** o feed RSS público do canal (lista e datas) e, com chave, a YouTube Data API (`videos.list`), que informa o que está ao vivo e separa transmissões de uploads comuns. Não há mais raspagem de HTML do YouTube.
- **Atualização:** o resultado fica guardado no banco (tabela `YoutubeSnapshot`) e é renovado no máximo a cada 60 segundos, por quem visitar a página. Se o YouTube falhar, vale o último resultado bom; o estado "ao vivo" é descartado se esse resultado tiver mais de 10 minutos. Com a página aberta, um script consulta `/videos/youtube/` a cada 60 s e troca o destaque quando a live começa ou termina, sem interromper quem já apertou play.
- **Vídeo fixo:** edite em **Conteúdo > Nossa igreja** (URL e título). Em branco, o destaque passa a ser a transmissão mais recente.

**Variáveis de ambiente** (Vercel e Render):

- `YOUTUBE_API_KEY` (opcional): sem ela o site funciona, mas sem o destaque ao vivo, e a pilha pode incluir vídeos que não são transmissões.
- `YOUTUBE_CHANNEL_ID` (opcional): padrão `UCnJeIwpnusCcbJa9nAInb8Q`, o canal da igreja.

**Como criar a chave** (gratuita; a cota é de 10.000 unidades por dia e este uso gasta no máximo 1.440):

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto.
2. Em "APIs e serviços > Biblioteca", ative **YouTube Data API v3**.
3. Em "Credenciais", crie uma **chave de API** e restrinja-a à YouTube Data API v3.
4. Defina o valor em `YOUTUBE_API_KEY` na Vercel (Production e Preview) e no Render. Nunca coloque a chave no repositório nem em arquivos públicos.

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
