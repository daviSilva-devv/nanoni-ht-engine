# NANONI — BASE OFICIAL V1

**Status:** FROZEN FOR IMPLEMENTATION (salvo alterações deliberadas de produto)
**Objetivo:** servir como fonte única de verdade para produto, arquitetura, banco, fluxos, testes e execução no Codex.
**Princípio-mãe:** **construir para muitos canais/comunidades; lançar com uma.**

---

## 0. COMO USAR ESTE DOCUMENTO

Esta Base é a autoridade do projeto. O Codex deve implementar o que está aqui e **não inventar escopo**.

Toda ideia nova durante a implementação deve receber um destes destinos:

1. `BLOCKER_V1` — sem isso não vende ou não funciona ponta a ponta.
2. `POST_LAUNCH` — útil logo depois de validar vendas.
3. `BACKLOG` — não codar antes do lançamento.

**Regra de parada:** quando o sistema conseguir `coletar → aprovar → publicar → vender → confirmar pagamento → liberar acesso` de forma confiável, a V1 termina. A próxima prioridade passa a ser tráfego, venda e validação.

---

# 1. VISÃO DO PRODUTO

A Nanoni vai operar uma rede de comunidades adultas 18+ no Telegram, começando por **uma comunidade** e podendo expandir para várias comunidades FREE/VIP sem reconstruir o sistema.

O produto não é “um bot de vídeo”. O produto é um motor com cinco responsabilidades:

1. **Content Engine** — encontrar, organizar, aprovar e preparar conteúdo.
2. **Publishing Engine** — publicar automaticamente FREE/VIP nos destinos corretos.
3. **Sales Engine** — conduzir o lead pelo caminho mais curto possível.
4. **Payment/Access Engine** — registrar pagamento e conceder/remover acesso.
5. **Operations Engine** — painel, métricas, alertas, moderação, histórico e contingência.

O sistema deve conseguir crescer de:

- 1 FREE + 1 VIP

para:

- vários FREE;
- vários VIP;
- várias comunidades;
- vários micronichos/tópicos;
- vários produtos, preços, upgrades e bundles;

**sem criar código específico para “Brasileiras”, “Casais”, “Gringas” ou qualquer outro nome comercial.**

---

# 2. PRINCÍPIOS NÃO NEGOCIÁVEIS

## 2.1. Configuração antes de código

Criar ou alterar os itens abaixo **não pode exigir VS Code**:

- nicho;
- micronicho;
- comunidade;
- canal FREE;
- grupo VIP;
- tópico;
- produto;
- versão do produto;
- preço;
- duração do acesso;
- promoção;
- add-on;
- CTA;
- copy;
- fonte;
- janela de publicação;
- quantidade de posts/packs;
- regras de moderação;
- regra de reoferta.

Tudo isso nasce do banco + painel.

## 2.2. Simplicidade operacional

O sistema deve reduzir a operação humana para algo próximo de:

`coletar candidatos → ✅/❌ → acabou`.

Depois da aprovação, a máquina assume download, processamento, vault, fila, agendamento e publicação.

## 2.3. Sem overengineering na V1

Não entram na V1:

- microsserviços distribuídos;
- Kubernetes;
- Redis obrigatório;
- IA conversacional aberta;
- CRM gigante;
- aplicativo mobile;
- recomendação por ML complexo;
- sistema de afiliados;
- multitenancy/SaaS;
- classificação visual sofisticada;
- dezenas de gateways;
- dezenas de sites fonte.

## 2.4. Operação legal 18+

A plataforma é somente para conteúdo adulto legal envolvendo adultos e uso autorizado/lícito do conteúdo. Devem existir regras duras contra:

- CSAM/conteúdo sexual envolvendo menores;
- sexualização de aparência infantil;
- conteúdo íntimo não consensual;
- doxxing;
- ameaça/violência criminal;
- material que viole claramente a lei ou termos críticos da infraestrutura utilizada.

A barra de pesquisa administrativa **não deve possuir blacklist ingênua de palavras**. Pesquisa interna e moderação pública são sistemas separados.

---

# 3. ESCOPO COMERCIAL INICIAL

## 3.1. Estrutura inicial

Lançamento:

- 1 comunidade;
- 1 canal FREE;
- 1 supergrupo VIP com Fórum/Tópicos;
- tópico Geral/Avisos;
- tópico Pedidos/Papo;
- alguns tópicos de micronichos;
- 1 bot comercial/acesso;
- 1 painel;
- 1 checkout/web storefront;
- 1 integração de pagamento real no lançamento.

A arquitetura suporta N comunidades, mas somente uma precisa estar ativa no primeiro lançamento.

## 3.2. Preços padrão iniciais

Configuração inicial sugerida:

- Semanal: **R$ 14,90**
- Mensal: **R$ 29,90**
- Lifetime: **R$ 37,90**

Nenhum valor é hardcoded. O painel controla preço, destaque visual e disponibilidade.

O Lifetime pode ser destacado como oferta principal de lançamento.

## 3.3. Lifetime e versões

Lifetime não significa acesso automático a todos os produtos futuros da Nanoni.

Modelo correto:

- `CommunityVersion A` é vendida hoje;
- usuário compra Lifetime de A;
- ele mantém entitlement de A conforme os termos de A;
- se A precisar ser migrada tecnicamente para outro grupo Telegram, o acesso continua;
- se a Nanoni lançar `CommunityVersion B` com mais micronichos/benefícios, B é um novo produto/upgrade;
- comprador antigo pode receber oferta de upgrade com preço reduzido.

Isso impede ambiguidade e evita que “Lifetime” destrua toda monetização futura.

---

# 4. TOPOLOGIA TELEGRAM

## 4.1. FREE

Cada comunidade pode possuir um ou mais destinos FREE, mas a V1 usa um.

Tipo preferencial: **canal Telegram**.

Função do FREE:

- aquisição;
- prévias;
- conteúdo curto completo;
- algumas fotos;
- alguns conteúdos completos selecionados;
- CTAs de venda;
- divulgação manual externa.

FREE não é o produto. FREE é distribuição/aquisição.

## 4.2. VIP

Cada produto/comunidade VIP usa um **supergrupo com Fórum/Tópicos**.

Exemplo lógico:

- Geral/Avisos
- Pedidos/Papo
- Micronicho A
- Micronicho B
- Micronicho C
- Micronicho D
- Micronicho E
- Micronicho F

O conteúdo VIP é publicado **dentro dos tópicos dos micronichos**.

## 4.3. Permissões dos membros

Membros podem:

- texto;
- respostas;
- reações;
- pedidos no tópico apropriado.

Membros não podem enviar:

- vídeos;
- fotos;
- documentos;
- áudios;
- mídias em geral, salvo alteração administrativa futura.

Admins/bot podem publicar mídia.

## 4.4. Proteção do nosso conteúdo

Os destinos próprios podem habilitar proteção de conteúdo quando isso fizer sentido operacionalmente.

Essa configuração é independente do collector.

---

# 5. MODELO DE DOMÍNIO COMERCIAL

O sistema deve trabalhar com entidades genéricas.

## 5.1. Niche

Tema amplo de organização.

Campos principais:

- id
- name
- slug
- description
- active
- sort_order

## 5.2. MicroNiche

Subcategoria dentro de um Niche/Community.

Campos:

- id
- niche_id
- name
- slug
- active

## 5.3. Community

Representa a comunidade comercial lógica, não um chat Telegram específico.

## 5.4. CommunityVersion

Snapshot imutável dos benefícios/micronichos prometidos numa oferta comercial.

Serve para:

- Lifetime;
- upgrades;
- reofertas;
- histórico de produto.

Nunca sobrescrever retroativamente a promessa de uma versão já vendida.

## 5.5. TelegramDestination

Representa infraestrutura concreta.

Tipos:

- `FREE_CHANNEL`
- `VIP_FORUM`
- `VAULT_CHANNEL`
- `ADMIN_ALERT_CHAT`

Campos incluem:

- telegram_chat_id
- username (se houver)
- logical_role
- status
- replacement_destination_id

Separar `CommunityVersion` de `TelegramDestination` permite trocar um grupo que caiu sem destruir os direitos comerciais existentes.

## 5.6. Topic

Mapeia micronicho ou função operacional a `message_thread_id`.

Exemplos:

- `CONTENT`
- `GENERAL`
- `REQUESTS`

## 5.7. Product

O que é comercialmente vendido.

Ex.: acesso à CommunityVersion X.

## 5.8. PricePlan

Planos:

- WEEKLY
- MONTHLY
- LIFETIME
- CUSTOM

Campos:

- amount
- currency
- duration_days nullable
- lifetime boolean
- active
- featured

## 5.9. Offer

Camada promocional genérica.

Pode expressar:

- desconto;
- add-on;
- bundle;
- upgrade;
- win-back;
- promoção temporária;
- oferta condicionada a produto previamente comprado.

Nada de lógica como `if product == brasileiras` no código.

---

# 6. SALES ENGINE / “X1”

## 6.1. Filosofia

O X1 não é chatbot de conversa longa.

É um **Sales Router**.

Objetivo do lead quente:

`entrada → desejo → escolha → checkout` com o mínimo de etapas.

Meta de UX: um lead decidido deve conseguir chegar ao checkout em segundos.

## 6.2. Primeira experiência

A primeira superfície do bot deve aceitar um **vídeo adulto de apresentação configurável**, seguido de copy curta e botões.

Slots iniciais configuráveis:

- hero_media
- hero_copy
- CTA_PRIMARY
- CTA_FREE
- CTA_PROMOTIONS
- CTA_ALREADY_BOUGHT

Exemplo de intenções, não de copy fixa:

- Quero VIP
- Ver Free
- Promoções
- Já comprei

## 6.3. Segmentação comportamental

Estados de lead:

- NEW
- AGE_CONFIRMED
- INTENT_VIP
- INTENT_FREE
- PRODUCT_VIEWED
- PLAN_SELECTED
- CHECKOUT_STARTED
- PAYMENT_PENDING
- PAYMENT_ABANDONED
- PAID
- ACCESS_PENDING
- CUSTOMER_ACTIVE
- UPSELL_ELIGIBLE
- EXPIRED_CUSTOMER
- WINBACK_ELIGIBLE

O sistema não precisa “conversar” para saber intenção; cliques/eventos já fornecem contexto.

## 6.4. Lead VIP direto

Fluxo ideal:

1. Entrada/18+.
2. Hero.
3. Quero VIP.
4. Escolha de produto/comunidade quando houver mais de uma.
5. Escolha do plano.
6. Checkout.
7. Pagamento confirmado.
8. Acesso.
9. Uma oferta de upsell/cross-sell opcional.
10. Silêncio.

## 6.5. Lead FREE

Fluxo:

1. Entrada/18+.
2. Hero.
3. Ver Free.
4. Vai ao FREE.
5. Conteúdo + CTA trazem de volta para intenção de compra.
6. O histórico é preservado.

## 6.6. Recuperação

Default inicial configurável:

- pagamento iniciado/pendente: 1 lembrete em ~15–30 min;
- segundo toque algumas horas depois;
- depois parar.

Não bombardear o lead.

## 6.7. Pós-compra

Após pagamento:

- liberar acesso primeiro;
- mostrar **uma** oferta complementar relevante;
- “Agora não” encerra o fluxo;
- nova reoferta somente quando houver motivo novo: tempo, produto novo, expiração ou campanha.

## 6.8. Recompra

A Nanoni guarda histórico do cliente para reconhecer:

- produto comprado;
- plano;
- recusas;
- checkout abandonado;
- produtos ainda não possuídos;
- última compra;
- elegibilidade a upgrade.

O objetivo é permitir uma nova venda semanas/meses depois sem tratar o cliente como lead novo.

---

# 7. COPY ENGINE

Copy não fica enterrada no código.

## 7.1. CopySlot

Slots sugeridos:

- BOT_HERO
- FREE_CTA
- VIP_CTA
- CHECKOUT_RECOVERY
- POST_PURCHASE_UPSELL
- WINBACK
- ACCESS_GRANTED
- ACCESS_EXPIRED
- FREE_POST_CAPTION
- VIP_PACK_CAPTION

## 7.2. CopyVariant

Cada slot pode ter N variantes.

Campos:

- text
- media_id opcional
- weight
- active
- valid_from/to
- product filter opcional

O sistema pode sortear variantes por peso e armazenar qual variante gerou cada clique/venda.

## 7.3. Tom

Tom padrão:

- curto;
- provocativo;
- forte;
- emojis;
- CTA claro;
- sensação de acesso fechado/exclusivo;
- sem textão.

O painel permite editar/adicionar/remover frases livremente.

A aplicação não deve possuir blacklist ingênua de palavras no editor ou na busca interna. Templates padrão, porém, devem evitar alegações factualmente falsas ou conteúdo ilegal.

---

# 8. CONTENT ENGINE — MODELO CENTRAL

A unidade central não é “vídeo”. É **ContentPack**.

## 8.1. MediaAsset

Tipos:

- VIDEO
- IMAGE
- GIF (futuro/compatível)

Metadados:

- source
- source_locator
- mime
- extension
- duration
- width
- height
- file_size
- bitrate quando disponível
- source_caption
- source_date
- local_path temporário
- sha256 após download
- telegram_file_id
- telegram_file_unique_id
- vault_message_id
- status

## 8.2. ContentPack

Pode conter:

- 1 vídeo;
- várias fotos;
- várias fotos + vídeos;
- múltiplos vídeos;
- qualquer combinação suportada.

Mantém ordem original.

Exemplo:

`foto 1 → foto 2 → foto 3 → vídeo 1 → vídeo 2`.

## 8.3. PackItem

Relaciona asset ao pack com:

- position
- role
- selected
- derivative_of

## 8.4. MediaManifest

Todo adapter de fonte deve produzir o mesmo contrato:

```text
MediaManifest
- source
- source_collection_id
- source_item_id
- source_url
- title/caption
- created_at
- pack metadata
- media[]
  - type
  - duration
  - size estimate
  - dimensions
  - thumbnail/reference
  - downloadable status
```

O Content Engine não precisa saber se veio de Erome, Telegram Helper ou upload manual.

---

# 9. FONTES / ADAPTERS

Interface conceitual:

```text
SourceAdapter
- inspect(locator)
- search(query, filters)
- list_collection(locator)
- get_manifest(item)
- acquire(asset)
```

V1:

1. `EromeAdapter`
2. `TelegramHelperAdapter`
3. `ManualUploadAdapter`

Futuro:

- adapters adicionais.

Nenhum adapter pode contaminar regras de publicação, vendas ou acesso.

---

# 10. EROME ADAPTER

## 10.1. Filosofia

**Index first, download later.**

Nunca baixar álbum inteiro para depois decidir se presta.

## 10.2. Fluxo

1. Usuário cola URL ou faz uma busca suportada.
2. Adapter inspeciona a página.
3. Retorna MediaManifest.
4. Painel mostra pack, quantidade de fotos/vídeos e metadata.
5. Usuário escolhe o que quer.
6. Só os itens aprovados entram na fila de aquisição.

## 10.3. Download

Download deve:

- ser assíncrono;
- usar chunks;
- limitar concorrência;
- ter retry exponencial;
- possuir timeout;
- validar tamanho quando disponível;
- retomar/reprocessar falha sem repetir todo o pack.

## 10.4. Dependência

Erome é uma fonte, não o produto.

Se mudar HTML ou ficar indisponível:

- adapter entra em DEGRADED/OFFLINE;
- painel alerta;
- resto do sistema continua funcionando.

---

# 11. TELEGRAM PROTEGIDO — HELPER

## 11.1. Premissa real do projeto

As fontes Telegram relevantes podem possuir “Restrict Saving Content”. Portanto, **Telegram normal não é rota principal da V1**.

## 11.2. Objetivo

Fazer o máximo possível de forma assistida e clean sem transformar a coleta em um projeto infinito.

## 11.3. Componentes

### Browser Extension / Helper

Chrome/Edge Manifest V3.

Responsabilidades permitidas da V1:

- identificar chat/canal atual;
- identificar mensagem/post;
- coletar metadata exposta pela interface;
- identificar album/grouped content quando possível;
- capturar link/contexto;
- enviar esse contexto para o bridge local;
- criar ação “Enviar para Nanoni”.

### Local Bridge

V1: serviço HTTP local em `127.0.0.1`, protegido por token por instalação.

Motivo: muito mais simples que Native Messaging para o primeiro release.

Futuro: trocar transporte por Native Messaging sem alterar `TelegramHelperAdapter`.

## 11.4. Importação assistida

Quando o arquivo não puder ser adquirido automaticamente de forma suportada:

1. Helper já cria o candidate no painel com contexto.
2. Operador fornece/importa o arquivo localmente.
3. Watch Folder associa o arquivo ao candidate.
4. Daí em diante tudo é automático.

Meta: exceção em poucos cliques, não fluxo manual de renomear/mover/configurar.

## 11.5. Licença de projetos de referência

Projetos GPL podem ser estudados como referência comportamental. **Não copiar código GPL para o componente proprietário sem decisão explícita de licenciamento.** Implementação preferencial: clean-room/original.

---

# 12. WATCH FOLDER / ARQUIVOS LOCAIS

Estrutura local sugerida:

```text
C:\Nanoni\media\
  inbox\
  processing\
  ready\
  failed\
  temp\
```

Regras:

- `inbox`: arquivos recém-importados;
- `processing`: em uso por job;
- `ready`: pronto para upload/vault;
- `failed`: falha que precisa de atenção;
- `temp`: previews/artefatos descartáveis.

Movimentação deve ser atômica quando possível.

Não usar a pasta Downloads do Windows como estado do sistema.

---

# 13. QUALIDADE — SEM FILTRO BURRO

Resolução, tamanho e duração são **metadados**, não julgamento automático.

O sistema pode rotular:

- LOW_RES
- HD
- FULL_HD
- SHORT
- MEDIUM
- LONG_FORM
- HEAVY
- LIGHT
- LIVE_STYLE

Mas não deve rejeitar automaticamente só porque:

- tem 480p;
- tem 30 minutos;
- tem 2 GB;
- formato é menos comum, se ainda for processável.

Auto-rejeição somente por critérios objetivos:

- arquivo corrompido;
- mídia inválida;
- duplicata confirmada;
- conteúdo explicitamente proibido pela política de segurança/compliance;
- aquisição impossível após limite de retries.

O operador decide o que “é bom”. Dados de aprovação/engajamento ajudam a ordenar, não substituem a decisão.

---

# 14. APROVAÇÃO

Tela de aprovação deve ser rápida.

Cada candidate mostra:

- preview/thumbnail;
- fonte;
- duração;
- tamanho;
- resolução;
- pack count;
- tags;
- source score;
- status.

Ações:

- APROVAR
- DESCARTAR
- DEPOIS
- FAVORITO opcional

Ao aprovar:

- escolher/confirmar Niche;
- escolher um ou mais MicroNiches;
- destino pretendido FREE/VIP;
- optar por pack inteiro ou subset;
- opcionalmente marcar criação de preview.

Suportar seleção em lote.

Conteúdo descartado continua registrado por fingerprint/source ID para não reaparecer imediatamente.

---

# 15. DEDUPLICAÇÃO

V1 usa camadas simples:

1. `source + source_item_id` — impede repetir mesmo item.
2. URL/source locator normalizado.
3. SHA-256 após download.
4. Telegram `file_unique_id` quando aplicável.

Backlog:

- fingerprint perceptual de frames para detectar reencodes/cópias cross-source.

Não atrasar lançamento por dedupe perfeito.

---

# 16. PREVIEWS / DERIVADOS

Um vídeo original pode gerar derivados.

V1:

- preview de duração configurável, default ~50s;
- start offset configurável, default 0;
- original preservado logicamente;
- preview marcado com `derivative_of`.

Uso:

- original → VIP;
- preview → FREE.

FFmpeg é o processador padrão.

Nunca sobrescrever o original temporário antes do upload/vault concluir.

---

# 17. TELEGRAM VAULT

Para não manter terabytes no PC, usar um **canal privado de Vault controlado pela Nanoni**.

Fluxo:

1. Asset aprovado é adquirido temporariamente no PC.
2. Processado/validado.
3. Upload para Vault.
4. Salvar `telegram_file_id`, `file_unique_id`, `vault_chat_id`, `vault_message_id`.
5. Publicações futuras reutilizam arquivo do Telegram quando possível.
6. Após confirmação de vault/publicação, arquivo local entra em purge.

Benefícios:

- PC não vira arquivo morto;
- conteúdo aprovado fica reutilizável;
- vários posts podem usar o mesmo asset sem novo download;
- packs continuam definidos no banco mesmo que assets sejam armazenados separadamente no Vault.

O Vault não substitui direitos/backup comercial; é cache operacional de mídia.

---

# 18. PUBLICATION ENGINE

## 18.1. PublicationRule

Configurável por destino e/ou tópico.

Campos:

- enabled
- target_destination
- target_topic
- content_type/pack requirements
- posts_per_day
- schedule windows
- random jitter
- minimum spacing
- priority

## 18.2. FREE

FREE usa horários **não rígidos**.

Modelo:

- janelas de tempo;
- pesos por janela;
- horário exato sorteado dentro da janela;
- maior peso à noite/madrugada.

Default inicial pode privilegiar:

- 20h–00h: forte
- 00h–03h: muito forte
- tarde: médio
- manhã: leve

Tudo configurável.

## 18.3. VIP / micronichos

Micronicho tem comportamento diferente.

Regra padrão:

- cada tópico de micronicho recebe um **pack por dia** ou conforme configuração;
- cada tópico possui uma janela diária;
- minuto exato é randomizado;
- sistema aplica espaçamento para não soltar tudo simultaneamente.

Exemplo conceitual:

- Topic A: janela 21h–23h
- Topic B: 22h–00h
- Topic C: 23h–01h
- Topic D: 00h–02h

Não hardcodar horários.

## 18.4. Fila vazia

Se a fila acabar:

- NÃO repostar lixo automaticamente;
- NÃO escolher aleatório já publicado sem regra;
- marcar alerta;
- pular job com status `SKIPPED_NO_CONTENT`.

Dashboard mostra estimativa de “dias de estoque”.

## 18.5. Publicação manual

Sempre existir:

- Publicar agora
- Adicionar à fila
- Agendar data/hora

Automação nunca elimina override manual.

---

# 19. ARQUIVOS GRANDES / BOT API LOCAL

O Media Worker deve suportar o **Telegram Bot API Server local**.

Objetivo:

- upload de arquivos grandes diretamente do PC;
- evitar limite do Bot API público;
- usar caminho local quando aplicável.

A decisão de usar local Bot API fica atrás de uma interface `TelegramMediaGateway`, permitindo fallback para API oficial quando o arquivo couber.

Regras:

- streaming/chunking;
- progresso;
- retry;
- idempotency key;
- nunca deletar local antes de confirmação Telegram.

---

# 20. CONTENT SCORE / APROVEITAMENTO

Objetivo: descobrir conteúdo que gera resposta real, não só “parece bonito”.

V1 armazena por publicação:

- reply_count
- unique_repliers
- reaction_count
- moderation_removed_replies
- published_at
- topic
- pack/content ids

Score inicial simples e configurável, priorizando **pessoas únicas respondendo**.

Exemplo conceitual:

`score = unique_repliers*4 + reply_count*1 + reaction_count*0.5`

Não tratar fórmula como verdade científica; armazenar métricas brutas para poder recalcular no futuro.

## 20.1. Source Score

Fonte ganha estatísticas:

- candidates shown
- approved
- approval_rate
- avg_content_score
- download_failure_rate

Uso: ordenar candidatos de fontes historicamente boas.

Nunca auto-banir fonte apenas por score baixo.

---

# 21. MODERAÇÃO

## 21.1. Objetivo

Permitir comunidade ativa sem exigir moderação manual 24/7.

## 21.2. V1 sem IA paga

Duas camadas:

1. regras determinísticas de alta confiança;
2. fila/alerta para termos ambíguos.

Membros já não podem enviar mídia, reduzindo muito risco.

## 21.3. Severity

- `INFO`
- `REVIEW`
- `HIGH`
- `CRITICAL`

Ações possíveis:

- log apenas;
- alertar admin;
- apagar mensagem;
- restringir temporariamente;
- banir.

Pedidos explícitos envolvendo menores/CSAM ou outras categorias inequivocamente ilegais devem receber tratamento crítico.

Termos isolados ambíguos não devem gerar ban automático sem contexto suficiente.

---

# 22. PAYMENT ENGINE — REGRA CRÍTICA

## 22.1. Abstração

```text
PaymentProvider
- create_charge()
- get_charge()
- verify_webhook()
- cancel_charge()
- refund() opcional
```

Implementações:

- `MockPaymentProvider` para testes;
- `PixProviderX` escolhido antes do lançamento;
- providers futuros sem alterar Orders/Access.

## 22.2. Gateway

O provider de produção precisa:

- aceitar explicitamente a categoria comercial adulta/high-risk legal;
- oferecer PIX dinâmico;
- webhook;
- consulta de cobrança;
- KYC compatível;
- política de saque/reserva conhecida.

Não esconder categoria comercial de PSP.

## 22.3. GATE DE COMPLIANCE TELEGRAM

**Fato arquitetural importante:** Telegram exige Stars para vendas de bens/serviços digitais feitas por bots ou mini apps dentro do Telegram.

Portanto, PIX não deve ser implementado como “invoice alternativo dentro do bot” sem validação explícita de compliance.

A Base suporta dois modos:

### `TELEGRAM_STARS`

Modo compatível para venda digital dentro do bot/mini app.

### `EXTERNAL_PIX`

A compra ocorre numa storefront/checkout web independente; o bot atua como:

- identidade/reconciliação;
- claim de compra já realizada;
- acesso;
- suporte.

**Antes do lançamento com PIX**, revisar os termos vigentes do Telegram e decidir como o tráfego chega ao checkout externo sem transformar o bot em um mecanismo alternativo de pagamento proibido.

Implementação técnica pode existir atrás de feature flag, mas não deve ser ativada cegamente.

---

# 23. ORDER / PAYMENT — ESTADOS

## 23.1. Order

```text
CREATED
CHECKOUT_READY
PAYMENT_PENDING
PAID
ACCESS_PENDING
FULFILLED
EXPIRED
CANCELLED
REFUNDED
REVIEW_REQUIRED
```

## 23.2. Payment

```text
CREATED
PENDING
CONFIRMED
FAILED
EXPIRED
REFUNDED
DUPLICATE_REVIEW
```

Pagamento e acesso são entidades separadas.

Webhook nunca “adiciona usuário no grupo diretamente”.

Webhook:

1. valida assinatura;
2. registra evento idempotente;
3. atualiza Payment;
4. emite job de fulfillment;
5. Access Engine processa entitlement.

---

# 24. IDEMPOTÊNCIA E EXCEÇÕES DE PAGAMENTO

Obrigatório:

- webhook repetido não duplica acesso;
- job repetido não duplica membership;
- ordem tem idempotency key;
- eventos externos têm unique constraint por provider/event id.

Casos:

## Pix confirmado sem webhook

Botão admin `RECHECK_PAYMENT` consulta provider.

## Pix “expirado” mas confirmado depois

Se provider confirma settlement válido, Order pode avançar para PAID.

## Pagamento duplicado

Registrar ambos; não dobrar entitlement automaticamente. Criar `REVIEW_REQUIRED`.

## Provider indisponível

Pedido permanece persistido e rechecável.

Nenhum dinheiro/evento pode “sumir”.

---

# 25. ACCESS ENGINE

## 25.1. Entitlement

É o direito comercial do cliente.

Campos:

- customer_id
- product_id
- community_version_id
- plan
- starts_at
- expires_at nullable
- status
- source_order_id

Estados:

```text
PENDING
ACTIVE
EXPIRED
REVOKED
SUSPENDED
```

Lifetime = `expires_at = null`, associado à CommunityVersion vendida.

## 25.2. MembershipGrant

Representa a materialização do entitlement num destino Telegram.

Separar isso permite trocar o chat sem perder o entitlement.

## 25.3. Entrada

Preferência:

- link de join request ou fluxo identificável;
- bot verifica Telegram user id;
- entitlement ativo → aprova;
- sem entitlement → nega.

Não usar username como identidade primária.

Identidade principal: `telegram_user_id`.

## 25.4. Reentrada

Usuário saiu acidentalmente:

- entitlement ainda ACTIVE → pode solicitar nova entrada.

## 25.5. Expiração

Semanal/mensal:

- scheduler detecta vencimento;
- entitlement → EXPIRED;
- remove usuário do destino;
- mantém histórico;
- pode criar elegibilidade de win-back.

---

# 26. QUANDO UM GRUPO/TÓPICO CAI

Infraestrutura e produto são separados.

## Destino indisponível

`TelegramDestination.status = DEGRADED/OFFLINE`.

Sistema:

- pausa publication jobs;
- gera alerta crítico;
- não apaga entitlement;
- permite cadastrar Replacement Destination.

## Migração técnica

Se é a mesma CommunityVersion em novo supergrupo:

- mapear replacement;
- reprocessar MembershipGrants;
- preservar compradores.

## Novo produto comercial

Se há novos micronichos/benefícios substanciais:

- criar nova CommunityVersion/Product;
- clientes antigos recebem upgrade offer, não entitlement automático.

---

# 27. PAINEL ADMINISTRATIVO V1

## 27.1. Dashboard

Mostrar em uma tela:

- receita hoje/7d/30d;
- pedidos;
- pagamentos confirmados;
- conversão;
- clientes ativos;
- vendas por produto;
- estoque de conteúdo por destino/tópico;
- dias estimados restantes;
- alertas críticos;
- jobs falhos.

## 27.2. Nichos/Comunidades

CRUD de:

- Niche
- MicroNiche
- Community
- CommunityVersion
- TelegramDestination
- Topic

## 27.3. Fontes

- adapters;
- fontes cadastradas;
- status;
- source score;
- última coleta;
- falhas.

## 27.4. Coleta

- URL/import;
- pedir candidatos;
- quantidade;
- fonte;
- recent/random quando aplicável;
- manifests encontrados.

## 27.5. Aprovação

Grid/swipe/list rápida com preview e metadata.

## 27.6. Biblioteca

- packs;
- assets;
- tags;
- destino;
- status;
- publicado onde;
- vault status.

## 27.7. Fila/Publicação

- próximas publicações;
- janelas;
- prioridades;
- publicar agora;
- pausar destino;

## 27.8. Produtos/Ofertas

- preços;
- planos;
- featured;
- upgrades;
- add-ons;
- bundles;

## 27.9. Copy

Editor de CopySlots/Variants.

## 27.10. Pedidos/Pagamentos

- status;
- recheck;
- liberar manualmente com AuditLog;
- cancelar;
- refund se provider suportar.

## 27.11. Clientes/Acessos

- histórico;
- produtos;
- entitlement;
- Telegram id;
- reentrada;
- remoção manual.

## 27.12. Alertas

“PRECISA DE ATENÇÃO”:

- pago sem acesso;
- webhook inválido/falho;
- fila vazia;
- destino Telegram offline;
- upload falhou;
- tópico inexistente;
- espaço local baixo;
- provider indisponível;

---

# 28. PAPÉIS ADMIN

Schema suporta:

- SUPERADMIN
- CONTENT_EDITOR
- SUPPORT

V1 pode ter somente SUPERADMIN ativo.

Permissões futuras já não devem exigir refatorar tabelas.

---

# 29. ARQUITETURA TÉCNICA

## 29.1. Estratégia

**Modular monolith + worker local.**

Sem microsserviços.

## 29.2. Control Plane

Responsável por:

- API do painel;
- bot comercial/acesso;
- clientes;
- produtos;
- orders/payments;
- webhooks;
- entitlement/access;
- copy;
- analytics;
- scheduler lógico;
- alertas.

Stack preferencial:

- Python 3.12+
- FastAPI
- SQLAlchemy 2
- Alembic
- aiogram
- PostgreSQL
- Pydantic

## 29.3. Media Worker

Roda no PC.

Responsável por:

- adapters de conteúdo;
- helper bridge;
- watch folder;
- downloads;
- ffprobe/FFmpeg;
- previews;
- upload ao Vault;
- publicações de mídia grandes;
- limpeza local.

## 29.4. Admin Web

- Next.js / React
- interface desktop-first responsiva
- tema claro por padrão
- foco em rapidez, cards, tabelas e preview

Não gastar semanas com design system próprio.

## 29.5. Browser Helper

- TypeScript/JavaScript
- Manifest V3
- bridge local via localhost na V1

## 29.6. Redis

**Não obrigatório na V1.**

Jobs persistidos no PostgreSQL + worker polling/locks.

Migrar para Redis/Celery/RQ somente quando houver volume que justifique.

---

# 30. ESTRUTURA DO REPOSITÓRIO

Sugestão:

```text
nanoni-engine/
  apps/
    control-plane/
    media-worker/
    admin-web/
  extensions/
    telegram-helper/
  packages/
    domain/
    integrations/
  migrations/
  scripts/
  tests/
    unit/
    integration/
    e2e/
  docs/
    BASE-OFICIAL.md
    ADR/
  docker-compose.yml
  README.md
```

Não criar dezenas de pastas vazias “para o futuro”.

---

# 31. BANCO — ENTIDADES PRINCIPAIS

Tabelas mínimas:

### Organização
- admin_users
- admin_roles
- settings

### Catálogo/comunidades
- niches
- microniches
- communities
- community_versions
- community_version_microniches
- telegram_destinations
- topics

### Comercial
- products
- price_plans
- offers
- offer_conditions
- offer_products
- copy_slots
- copy_variants

### Conteúdo
- sources
- source_profiles
- content_candidates
- content_packs
- media_assets
- pack_items
- content_tags
- content_pack_tags
- content_pack_microniches
- approvals
- derivatives
- vault_objects

### Publicação
- publication_rules
- schedule_windows
- publication_jobs
- publications
- publication_metrics

### CRM/vendas
- customers
- customer_telegram_identities
- leads
- lead_events
- orders
- order_items
- payments
- payment_events
- entitlements
- membership_grants
- invite_records

### Operação
- moderation_rules
- moderation_events
- jobs
- alerts
- audit_logs
- integration_credentials_metadata

Segredos reais não ficam em tabela em plaintext.

---

# 32. JOB ENGINE

Jobs persistidos:

- DISCOVER_SOURCE
- ACQUIRE_MEDIA
- PROBE_MEDIA
- GENERATE_PREVIEW
- UPLOAD_VAULT
- PUBLISH_CONTENT
- REFRESH_METRICS
- RECHECK_PAYMENT
- FULFILL_ACCESS
- EXPIRE_ACCESS
- REPAIR_MEMBERSHIP
- CLEAN_LOCAL_MEDIA
- SEND_SALES_FOLLOWUP

Estados:

```text
QUEUED
RUNNING
SUCCEEDED
FAILED_RETRYABLE
FAILED_FINAL
CANCELLED
SKIPPED
```

Campos essenciais:

- id
- type
- payload
- status
- attempts
- max_attempts
- run_after
- locked_at
- lock_owner
- idempotency_key
- last_error

---

# 33. EVENTOS DE DOMÍNIO

Registrar eventos importantes:

- LEAD_STARTED
- INTENT_SELECTED
- FREE_CLICKED
- PRODUCT_VIEWED
- PLAN_SELECTED
- CHECKOUT_STARTED
- PAYMENT_CREATED
- PAYMENT_CONFIRMED
- ACCESS_GRANTED
- ACCESS_EXPIRED
- UPSELL_SHOWN
- UPSELL_ACCEPTED
- CONTENT_APPROVED
- CONTENT_PUBLISHED
- CONTENT_REPLIED
- MODERATION_TRIGGERED

Analytics deriva desses eventos, evitando lógica espalhada.

---

# 34. MÉTRICAS DE NEGÓCIO

Prioridade:

1. receita;
2. Pix/payment confirmado;
3. conversão checkout → pago;
4. FREE → checkout;
5. receita por membro/lead FREE;
6. recompra;
7. upsell/cross-sell;
8. produto mais rentável;
9. conteúdo que gera intenção/comentários.

Views sozinhas não decidem estratégia.

Atribuição:

- cada CTA/copy/post pode carregar campaign id;
- lead_events preservam source/campaign;
- order registra attribution quando disponível.

---

# 35. SEGURANÇA

## 35.1. Segredos

- `.env` fora do git;
- provider keys fora do frontend;
- token do helper por instalação;
- Telegram bot token somente backend;
- API ID/hash e sessões protegidas localmente.

## 35.2. Admin

- senha forte;
- sessão segura;
- TOTP/2FA recomendado;
- ações críticas com AuditLog.

## 35.3. Webhooks

- verificar assinatura/provider secret;
- body bruto quando provider exigir;
- dedupe de event id;
- rate limit.

## 35.4. Helper local

- bind apenas `127.0.0.1`;
- token aleatório;
- CORS/origin restrito;
- não expor bridge via Cloudflare Tunnel.

---

# 36. LOGS E AUDITORIA

Logs estruturados com:

- timestamp
- level
- component
- correlation_id
- job_id
- order_id quando houver
- content_pack_id quando houver
- message curta
- stack/error sanitizado

AuditLog para ações humanas:

- liberar acesso manual;
- remover cliente;
- mudar preço;
- trocar destino;
- cancelar/refund;
- alterar permissão;
- apagar conteúdo.

---

# 37. BACKUP E RECOVERY

Backup obrigatório:

- PostgreSQL;
- configurações;
- mappings Telegram;
- products/offers/copy;
- entitlements/orders/payments;

Não é obrigatório backup local de todos os vídeos temporários.

Vault + source references servem como retenção operacional quando possível.

Rotina:

- backup diário automático do DB;
- retenção rotativa;
- teste de restore antes do lançamento.

---

# 38. LIMPEZA / QUOTA DO PC

Configurações:

- max_temp_gb
- min_free_disk_gb
- purge_after_vault_hours
- failed_retention_days

Se espaço cair abaixo do limite:

- pausar novos downloads;
- finalizar uploads em andamento quando seguro;
- alerta crítico;
- nunca deletar asset ainda necessário por job ativo.

---

# 39. CONTINGÊNCIA

## PC reiniciou

Jobs persistentes retomam; arquivos ficam em estado coerente por pasta/job.

## Bot comercial caiu

Orders/payments continuam persistidos; processamento recomeça ao voltar.

## Media Worker caiu

Vendas/acesso não devem depender do worker de mídia quando Control Plane estiver separado.

## Telegram Bot API local caiu

Upload job retry; não apaga local.

## Tópico apagado

Destino marcado DEGRADED; publicação pausa; painel exige remapeamento.

## Grupo caiu

Entitlements preservados; replacement destination.

## Gateway caiu

Checkout/provider fica DEGRADED; nenhum pedido é apagado.

## Webhook duplicado

Idempotência.

## Webhook não chegou

Recheck provider.

## Conteúdo falhou

Vai para `failed`, alerta e mantém candidate/pack.

---

# 40. CUSTO / DEPLOYMENT

Objetivo: quase zero antes de provar receita.

## Fase de validação

Pode rodar:

- Control Plane local;
- Media Worker local;
- PostgreSQL local;
- Bot API Server local;
- Cloudflare Tunnel apenas para endpoints públicos necessários;
- domínio barato.

Requisito operacional: PC ligado durante validação/tráfego.

## Após vendas

Mover somente Control Plane + PostgreSQL para **um** host pequeno always-on.

Media Worker continua no PC.

Não pagar duas VPS para mídia.

Custos recorrentes principais:

- domínio;
- taxa do provider de pagamento;
- eventual host único quando receita justificar.

---

# 41. V1 — O QUE ENTRA

V1 deve entregar:

1. CRUD de niche/microniche/community/version.
2. Configurar canal FREE, grupo VIP e tópicos.
3. Produtos e planos.
4. Copy configurável.
5. Erome inspect/import seletivo.
6. Manual/Helper assisted import Telegram.
7. Watch Folder.
8. Packs foto+vídeo.
9. Aprovação.
10. Preview simples.
11. Vault.
12. Publication Engine.
13. Horários randomizados FREE.
14. Pack por tópico/micronicho.
15. Bot de entrada/18+/navegação.
16. Sales Router baseado em eventos.
17. PaymentProvider interface + mock.
18. Provider real antes do lançamento.
19. Orders/Payments idempotentes.
20. Entitlements.
21. Join request/access.
22. Expiração semanal/mensal.
23. Lifetime por CommunityVersion.
24. Reentrada.
25. Um upsell pós-compra.
26. Recuperação simples de checkout.
27. Content Score básico.
28. Moderação determinística básica.
29. Dashboard.
30. Alertas.
31. AuditLog.
32. Backup/restore testado.
33. E2E de venda real.

---

# 42. NÃO ENTRA NA V1

- IA conversacional aberta.
- classificação visual AI.
- auto-corte inteligente por cena.
- perceptual dedupe avançado.
- afiliados.
- app mobile.
- multiempresa.
- marketplace.
- múltiplos providers ativos simultaneamente.
- Pix Automático recorrente.
- automação sofisticada de pricing.
- ML para melhor horário.
- Native Messaging obrigatório.
- scraping de dezenas de sites.
- automação agressiva de Protected Telegram que transforme bypass em dependência central.

Tudo isso vai ao backlog.

---

# 43. ORDEM EXATA DE IMPLEMENTAÇÃO PARA O CODEX

## FASE 0 — Foundation

Entregar:

- repo;
- ambiente;
- PostgreSQL;
- migrations;
- config;
- logging;
- job table;
- testes base.

**Gate:** testes e migrations funcionando do zero.

## FASE 1 — Domain/Admin Core

Entregar entidades:

- niche/microniche;
- community/version;
- destinations/topics;
- product/price plan/offer;
- copy.

Painel CRUD funcional.

**Gate:** criar nova comunidade completa sem alterar código.

## FASE 2 — Content Core

- MediaManifest;
- candidate;
- pack/assets;
- manual upload;
- Watch Folder;
- approval;
- local state machine.

**Gate:** importar arquivo e aprovar pack ponta a ponta.

## FASE 3 — Erome Adapter

- inspect;
- manifest;
- seletivo;
- async acquisition;
- retry;

**Gate:** álbum com foto+vídeo vira pack sem baixar o não selecionado.

## FASE 4 — Vault + Publisher

- Bot API gateway;
- Vault;
- Telegram destinations/topics;
- publicação manual;
- pack publishing;
- file reference storage.

**Gate:** pack aprovado sai no tópico correto e local é purgado somente após confirmação.

## FASE 5 — Scheduler

- publication rules;
- random windows;
- microniche daily packs;
- queue empty alerts.

**Gate:** 24h simuladas sem duplicar/postar fora da janela.

## FASE 6 — Telegram Helper

- MV3 extension;
- localhost bridge;
- context import;
- assisted import linkage.

**Gate:** post visto no Telegram vira candidate Nanoni com poucos cliques.

## FASE 7 — Bot / Sales Router

- age gate;
- hero media;
- copy variants;
- button routing;
- lead events;
- FREE flow;
- product discovery.

**Gate:** lead quente chega à etapa comercial sem conversa desnecessária.

## FASE 8 — Payment + Access

- PaymentProvider;
- Mock;
- provider real;
- checkout external mode;
- webhook;
- idempotência;
- entitlement;
- join requests;
- expiry/reentry.

**Gate:** pagamento real pequeno de teste concede acesso exatamente uma vez.

## FASE 9 — Upsell/Recovery

- 1 recovery;
- 1 second recovery;
- 1 post-purchase upsell;
- opt-out/cadence protection.

**Gate:** nenhuma sequência duplica após restart.

## FASE 10 — Engagement/Moderation/Metrics

- replies;
- unique repliers;
- reactions;
- score;
- basic moderation;
- dashboard metrics.

## FASE 11 — Hardening

- backups;
- restore;
- failure drills;
- security;
- disk quota;
- alert chat;
- launch checklist.

**Gate final:** Definition of Done V1.

---

# 44. TESTES OBRIGATÓRIOS

## Unit

- pricing/offer eligibility;
- entitlement expiry;
- idempotency;
- state transitions;
- schedule window selection;
- copy selection;
- score calculation.

## Integration

- Postgres migrations;
- Erome adapter fixture;
- FFmpeg preview;
- Telegram API mock/test environment;
- provider webhook fixture;
- helper bridge auth.

## E2E

### Conteúdo

`source → manifest → approve → acquire → vault → schedule → publish → purge`.

### Venda

`lead → checkout → payment → entitlement → join → active`.

### Expiração

`active → expires → removed → winback eligible`.

### Falha

- webhook 3x;
- worker reinicia;
- upload falha;
- grupo offline;
- tópico apagado;
- pouco disco.

---

# 45. DEFINITION OF DONE V1

A V1 está pronta quando todos forem verdadeiros:

- [ ] criar uma comunidade pelo painel sem código;
- [ ] criar micronichos/tópicos pelo painel;
- [ ] importar um pack público de fonte web;
- [ ] importar um item via helper/assisted flow;
- [ ] aprovar conteúdo;
- [ ] gerar preview;
- [ ] enviar ao Vault;
- [ ] publicar no FREE automaticamente;
- [ ] publicar packs nos tópicos VIP automaticamente;
- [ ] membros VIP conseguem texto/reação mas não mídia;
- [ ] fila vazia gera alerta e não lixo;
- [ ] bot tem hero media + copy + botões configuráveis;
- [ ] cliente entra na jornada comercial;
- [ ] checkout real funciona no modo aprovado para produção;
- [ ] pagamento confirmado uma vez cria um entitlement;
- [ ] acesso Telegram é concedido;
- [ ] semanal/mensal expira e remove corretamente;
- [ ] lifetime não expira naquela versão;
- [ ] cliente ativo consegue reentrar;
- [ ] upsell não bloqueia entrega principal;
- [ ] webhook duplicado não duplica nada;
- [ ] restart não perde jobs;
- [ ] banco possui backup e restore testado;
- [ ] dashboard mostra dinheiro, pagamentos, acesso, fila e alertas;
- [ ] existe pelo menos uma compra real de teste ponta a ponta.

**Quando esta lista estiver verde: congelar feature e divulgar.**

---

# 46. CRITÉRIO DE CONTINUAR OU MATAR UM NICHO

Não decidir por sentimento nem só views.

Após volume mínimo de teste, observar:

- FREE → intenção/checkout;
- checkout → pagamento;
- receita por lead/membro;
- custo de aquisição, se houver;
- recompra;
- reclamação/refund;
- capacidade de abastecer conteúdo;
- engagement do VIP.

O objetivo da V1 é gerar informação real para decidir se vale expandir.

---

# 47. BACKLOG PÓS-RECEITA

Prioridade sugerida somente depois de validar venda:

1. segundo produto/comunidade;
2. melhores upgrades/cross-sell;
3. win-back;
4. perceptual duplicate detection;
5. ranking automático por Content Score;
6. novos adapters;
7. Native Messaging;
8. Pix recorrente/novo provider se comercialmente permitido;
9. IA de moderação contextual;
10. IA de copy/segmentação sob regras rígidas;
11. classificação automática de conteúdo;
12. analytics de cohort/LTV;
13. operação multi-worker.

---

# 48. COISAS QUE O CODEX NÃO PODE FAZER SEM AUTORIZAÇÃO

- trocar stack principal;
- adicionar Redis “porque sim”;
- criar microsserviço;
- renomear conceitos de domínio sem necessidade;
- hardcodar nomes de nichos;
- criar feature não descrita;
- remover AuditLog;
- misturar Payment com Access;
- apagar arquivo antes de Vault/publication confirmada;
- implementar filtro subjetivo automático de qualidade;
- colocar segredo em repositório;
- transformar adapter específico em dependência do domínio;
- implementar IA conversacional;
- construir bypass de proteção como dependência crítica do produto;
- ativar método de pagamento em produção sem gate de compliance/provider.

Se encontrar problema estrutural, o Codex deve **documentar o conflito e propor a menor alteração possível**.

---

# 49. ADRs — DECISÕES ARQUITETURAIS QUE DEVEM SER REGISTRADAS

Criar pequenos ADRs para decisões que alterem fundação:

- ADR-001 Modular Monolith
- ADR-002 PostgreSQL Jobs Without Redis V1
- ADR-003 MediaManifest Adapter Contract
- ADR-004 CommunityVersion vs TelegramDestination
- ADR-005 Payment vs Entitlement Separation
- ADR-006 Vault Strategy
- ADR-007 Protected Telegram Assisted Import
- ADR-008 External Pix Compliance Gate

ADRs curtos: contexto, decisão, consequências.

---

# 50. PRIMEIRO CENÁRIO DE ACEITAÇÃO REAL

A demonstração final da V1 deve ser gravável em uma única sequência:

1. Admin abre painel.
2. Abre comunidade de lançamento.
3. Cola um álbum fonte autorizado com fotos + vídeos.
4. Sistema mostra pack sem baixar tudo.
5. Admin seleciona os itens e aprova.
6. Worker baixa somente os escolhidos.
7. Preview é criado.
8. Assets sobem ao Vault.
9. Original entra no tópico VIP correto.
10. Preview/foto entra na fila FREE em horário randomizado.
11. Lead chega ao funil.
12. Checkout autorizado é aberto.
13. Pagamento é confirmado.
14. Order vira PAID.
15. Entitlement vira ACTIVE.
16. Usuário pede entrada.
17. Bot aprova.
18. Dashboard mostra venda e cliente ativo.
19. Arquivos locais grandes são removidos.
20. Reiniciar serviços não duplica publicação nem acesso.

Se isso funcionar, existe produto vendável.

---

# 51. REGRA FINAL DO PROJETO

A Nanoni não vai vencer porque escreveu mais código.

Vai vencer se conseguir repetir, com pouco trabalho:

`conteúdo bom → atenção → oferta → pagamento → acesso → nova oferta futura`.

Portanto:

> **A arquitetura deve permitir crescer sem remendo, mas a implementação deve terminar cedo o suficiente para existir venda.**

**Construir para 100 comunidades. Lançar com 1.**

---

# 52. REFERÊNCIAS TÉCNICAS VERIFICADAS NA PREPARAÇÃO DA BASE

Pontos verificados antes do freeze:

- Telegram suporta supergrupos com tópicos/fórum e envio a tópicos específicos.
- Bot admin consegue acompanhar reações e operar permissões/restrições de membros.
- Telegram suporta join requests e aprovação por admin/bot.
- Telegram possui Bot API Server local com vantagens para arquivos grandes.
- Telegram exige Stars para vendas digitais realizadas dentro de bots/mini apps; PIX precisa de desenho externo/compliance validado.
- Chrome Extensions podem conversar com componentes locais; V1 escolhe bridge localhost por simplicidade e preserva transporte abstrato.
- Erome adapters públicos demonstram o padrão “inspecionar HTML/manifesto → escolher → baixar em chunks/retry”, que deve ser reimplementado de forma própria.

---

# 53. INSTRUÇÃO CURTA PARA O CODEX

Quando começar a implementação, usar esta regra:

> Leia `docs/BASE-OFICIAL.md` por completo. Implemente somente a fase solicitada. Não avance para a fase seguinte. Antes de alterar código, liste os acceptance criteria daquela fase. Ao terminar, rode testes, apresente arquivos modificados, decisões tomadas, pendências reais e confirme explicitamente se o gate da fase passou. Ideias fora do escopo devem ir para `docs/BACKLOG.md`, não para o código.


---

# 54. FIXTURES / REFERÊNCIAS PRÁTICAS JÁ DEFINIDAS

## Erome fixture inicial

Usar como fixture manual inicial de inspeção do adapter, sem colocar dependência no domínio:

`https://www.erome.com/Kkkkkkkmkk`

A fixture serve para testar:

- inspect;
- detecção de pack;
- fotos + vídeos;
- seleção antes de download;
- aquisição seletiva;
- Vault/publicação.

## Telegram Helper — referência de pesquisa

Projeto estudado como referência de UX/comportamento:

`Neet-Nestor/Telegram-Media-Downloader`

O repositório é GPL-3.0. Usar para entender padrões e limitações do Telegram Web; evitar copiar código para componente proprietário sem decisão explícita sobre licenciamento.

