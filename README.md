# IBR Canaa Landing Page

Landing page premium desenvolvida com Astro, TypeScript e Tailwind CSS para a Igreja Batista Regular Canaa.

## Tecnologias

- Astro 6
- TypeScript
- Tailwind CSS 4
- HTML semantico
- JavaScript leve para menu mobile, scroll reveal, eventos e validacao do formulario

## Estrutura principal

```txt
src/
├── components/
│   ├── Header.astro
│   ├── Hero.astro
│   ├── Benefits.astro
│   ├── About.astro
│   ├── HowItWorks.astro
│   ├── Features.astro
│   ├── Testimonials.astro
│   ├── FAQ.astro
│   ├── FinalCTA.astro
│   ├── ContactForm.astro
│   ├── Footer.astro
│   └── Icon.astro
├── data/
│   └── landing.ts
├── layouts/
│   └── MainLayout.astro
├── pages/
│   ├── index.astro
│   └── obrigado.astro
└── styles/
    └── global.css
```

Arquivos React antigos foram isolados em `src/legacy` e excluidos da checagem TypeScript.

## Como rodar

```bash
npm install
npm run dev
```

Acesse `http://localhost:4321/ibrcanaa/` ou a URL exibida pelo Astro no terminal.

## Build

```bash
npm run build
npm run preview
```

O projeto esta configurado com `base: /ibrcanaa` para publicacao no GitHub Pages.

## Formulario e backend futuro

O formulario esta em `src/components/ContactForm.astro` com validacao HTML e JavaScript basico. Hoje ele envia para `/obrigado/` usando `GET` para demonstracao.

Para integrar com FastAPI ou Flask:

1. Troque `method="get"` para `method="post"`.
2. Troque `action="/ibrcanaa/obrigado/"` pela URL da API, por exemplo `https://api.seudominio.com/leads`.
3. No backend, aceite os campos `name`, `email`, `whatsapp`, `interest`, `message` e `source`.
4. Retorne sucesso e redirecione para `/ibrcanaa/obrigado/` ou exiba feedback inline.

## SEO e performance

- Meta title e description no `MainLayout.astro`.
- Open Graph e Twitter Card basicos.
- Apenas um H1 na pagina principal.
- Secoes semanticas e conteudo escaneavel.
- CSS gerado pelo Tailwind e JavaScript minimo.
- Imagens com `alt`.

## Pontos preparados

- Eventos de analytics via `data-analytics`.
- Fila placeholder para Meta Pixel em `MainLayout.astro`.
- Depoimentos mockados em `src/data/landing.ts`.
- Botao flutuante de WhatsApp.
- Pagina de obrigado.

## Melhorias futuras

1. Substituir depoimentos mockados por relatos reais autorizados.
2. Atualizar telefone, redes sociais e enderecos reais em `src/data/landing.ts`.
3. Integrar formulario com FastAPI ou Flask.
4. Configurar Google Analytics, Meta Pixel e eventos de conversao reais.
5. Criar imagens sociais dedicadas para Open Graph.
6. Rodar Lighthouse/PageSpeed depois do deploy e ajustar imagens, cache e fontes se necessario.
