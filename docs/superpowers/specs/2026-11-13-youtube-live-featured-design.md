# Destaque ao vivo na home e troca da raspagem do YouTube pelo feed RSS

Data: 2026-11-13. Estado: aguardando aprovação.

## Intenção

Quem entra no site durante o culto deve ver a transmissão ao vivo no destaque
grande. Fora do ar, o destaque é um vídeo fixo escolhido pela igreja. Quando a
live termina, ela vai para a pilha lateral, como as demais transmissões.

Hoje a home raspa o HTML interno do YouTube (`ytInitialData`). Isso quebra sem
aviso e, quando quebra, mostra vídeos de reserva velhos (06 e 13/09/2026). O
desenho abaixo troca isso por fontes estáveis.

## Comportamento (decidido com o Washington)

| Situação | Destaque grande | Pilha lateral (3 itens) |
|---|---|---|
| Nada ao vivo | Vídeo fixo (inicialmente https://youtu.be/i7tGR33yy-o, "PodcastCanaã #01") | 3 transmissões mais recentes |
| Ao vivo | A live, com selo "Ao vivo agora" | 3 transmissões mais recentes, sem a live |
| Live termina | Volta ao vídeo fixo | A live encerrada passa a ser o 1º da pilha |

## Objetivos

- Detectar a live automaticamente e mostrar no destaque.
- A página aberta troca sozinha quando a live começa ou termina (consulta a
  cada 60 s), sem interromper quem já está assistindo.
- O vídeo fixo é editável pela equipe no painel, sem deploy.
- Nenhum visitante espera rede externa na maior parte das visitas.
- Sem chave de API o site continua funcionando, só sem o destaque ao vivo.
- O endpoint `/videos/youtube/`, usado pela página do GitHub Pages, continua
  compatível.

## Não objetivos

- Avisos ou notificações de live, chat, mais de uma live simultânea.
- Mostrar lives agendadas (`upcoming`) como se estivessem no ar.
- Login do YouTube (OAuth). Só leitura pública.

## Anti-objetivos (o que seria falha mesmo funcionando)

- Voltar a raspar HTML do YouTube.
- Mostrar vídeos de reserva velhos como se fossem recentes.
- Expor a chave da API ao navegador ou gravá-la no repositório.
- Um visitante ficar preso numa live que já acabou.

## Restrições

- Django 6, Python 3.14, hospedagem gratuita sem tarefas agendadas
  (Vercel e Render), então nada depende de cron.
- O cache precisa ser compartilhado entre instâncias; o cache em memória por
  processo não serve. O Neon já é comum a todas.
- Cota da API: 10.000 unidades por dia. `videos.list` custa 1. Com atualização
  no máximo a cada 60 s são no máximo 1.440 por dia.
- ID do canal (público): `UCnJeIwpnusCcbJa9nAInb8Q`.

## Abordagens consideradas

1. **RSS + YouTube Data API só para o estado ao vivo (escolhida).** O RSS dá a
   lista com datas e a API informa `liveBroadcastContent` e separa transmissões
   de uploads comuns (`liveStreamingDetails`). Exige uma chave gratuita.
2. Botão manual no painel. Sem chave, mas depende de alguém ligar e desligar,
   e a pilha pode misturar uploads. Descartada.

Vídeo fixo: **campo editável** na página "Nossa igreja" (escolhido) contra
constante no código (descartada: cada troca exigiria publicar de novo).

## Desenho

- **`core/youtube.py` (novo).** Lê o RSS (`/feeds/videos.xml?channel_id=...`) e,
  havendo chave, consulta `videos.list` (`snippet,liveStreamingDetails`) dos
  ids do feed. Ao vivo = `liveBroadcastContent == "live"`. Transmissão = tem
  `liveStreamingDetails`. Timeouts curtos (2 s cada) e leitura limitada em
  tamanho.
- **Instantâneo compartilhado.** Um modelo pequeno guarda o último resultado
  (JSON e `fetched_at`). Se tiver mais de 60 s, a requisição tenta atualizar;
  se falhar, serve o último bom. Se o último bom tiver mais de 10 min e a
  atualização continuar falhando, o estado "ao vivo" é descartado.
- **Montagem da lista.** Destaque = live, se houver; senão o vídeo fixo. Pilha
  = 3 transmissões mais recentes, sem repetir o destaque. Sem chave, a pilha
  usa os 3 itens mais recentes do RSS, que podem incluir uploads comuns.
- **Endpoint `/videos/youtube/`.** Mantém `videos` com o destaque em primeiro e
  a pilha depois, então o JavaScript atual da página do GitHub Pages já mostra
  o resultado certo. Acrescenta `live` (booleano).
- **Home.** Mesma ordem e selo "Ao vivo agora". Um script pequeno consulta o
  endpoint a cada 60 s com a aba visível. Só troca o destaque se o estado
  mudou e o visitante ainda não iniciou o player.
- **Vídeo fixo.** Campos `featured_video_url` e `featured_video_title` em
  `ChurchAboutPage`, com migration e valores iniciais do podcast; o id é
  extraído com o mesmo tratamento já usado nas aulas.
- **Configuração.** `YOUTUBE_API_KEY` (opcional) e `YOUTUBE_CHANNEL_ID`
  (padrão acima), por variável de ambiente. A chave só é usada no servidor.
- **Remoção.** Sai a raspagem (`_get_youtube_videos_from_page`) e a lista de
  vídeos de reserva de setembro. Sem nenhum dado e sem instantâneo, a home
  mostra só o vídeo fixo e o link do canal.

## Minhas decisões (conferir)

- Atualização a cada 60 s e expiração do "ao vivo" em 10 min.
- Selo "Ao vivo agora" no destaque e "Em destaque" para o vídeo fixo.
- Parser XML da biblioteca padrão, com tamanho limitado (a fonte é o YouTube).
- Instantâneo em modelo próprio, e não em tabela de cache do Django, para não
  exigir `createcachetable` no `build.sh`.

## Para o construtor

- Detalhes de HTML/CSS do selo e do script de consulta.
- Atualizar o texto baked de `pages/index.html` (lista de setembro) para o
  novo estado inicial.
- Documentar no README a criação da chave (Google Cloud: ativar "YouTube Data
  API v3", criar chave, restringir à API) e as variáveis de ambiente.
- Testes: ao vivo, agendada, nenhuma; filtro de transmissões; deduplicação;
  sem chave; erro da API mantém o último bom; expiração do "ao vivo";
  compatibilidade do endpoint; campo do painel.

## Dependências externas

- O Washington cria a chave da API e define `YOUTUBE_API_KEY` na Vercel e no
  Render. O código funciona antes disso, sem o destaque ao vivo.
