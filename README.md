# dor

CLI de imersão em **romeno** para quem fala **português**.

*`Dor`* é a palavra romena para saudade — o único par perfeito entre os dois idiomas,
e a tese do projeto: o atalho de um brasileiro para o romeno é o latim que sobrou nos dois.

---

## Estado atual

**Completo — F0 a F16.** O app estuda, ouve, corrige, agenda, pontua, guarda
tudo, monta os episódios que você leva no celular, mostra onde você está
tropeçando, ensina o país junto com o idioma — e deixa você levar o material
embora.

```bash
dor                     # ⭐ onde você está e o que fazer agora
dor review              # ⭐ sessão de estudo; o modo sobe conforme o item amadurece
dor drill --list        # ⭐ regras de gramática e quantos exercícios cada uma gera
dor drill g.verb.conjunctiv  #  o 'să' que substitui o infinitivo do português
dor drill g.pron.dativ -t    #  só ler a regra, sem treinar
dor listen              # ⭐ ditado e escuta ativa, com [r] para repetir
dor pairs               # ⭐ pares mínimos: pește/peste, față/fată, râu/rău
dor shadow              # ⭐ shadowing: devagar → sua vez → velocidade normal
dor podcast -t bebida   # ⭐ episódio MP3 bilíngue, com transcrição e playlist
dor export-audio -d a1_casa  #  um MP3 por palavra, para o celular
dor punte               # ⭐ as pontes que transformam português em romeno
dor lupta               # ⭐ Boss Battle: suas palavras fracas, com vidas contadas
dor stats               # ⭐ painel: calendário, temas fracos, melhor horário
dor export-anki -d a1_casa   #  leva o acervo para o Anki (TSV + mídia)
dor settings --meta 200 #    preferências
dor backup              #    salva o progresso (e --restaurar traz de volta)
dor undo                #    desfaz a última resposta e reagenda o item
dor destravar           #    tira a marca de 'travado' de um item que voltou

dor zi acasa            # ⭐ cenas do dia a dia: diálogo, rua e etiqueta
dor lyrics miorita      # ⭐ Lyrics Lab: folclore e poesia, com exercício
dor istorie cafea       # ⭐ de onde vem esta palavra?
dor livros              # ⭐ biblioteca graduada, do Creangă ao Cărtărescu
dor versuri             # ⭐ música parte por parte, do seu acervo pessoal
dor jurnal              # ⭐ o jornal da semana em romeno, com glossário
dor atualizar           # ⭐ traz o lote da semana para o acervo pessoal

dor doctor              # diagnóstico: Python, conteúdo, TTS, agendador, banco
dor validate            # valida todos os JSON e as referências cruzadas
dor list --pos noun     # navega o vocabulário (level, pos, gender, register, tag, deck)
dor show dor            # ficha completa da palavra + pronúncia
dor say "Bună ziua"     # síntese de voz em romeno
dor slang -k proverb    # gíria, expressões e provérbios com espelho em PT-BR
dor music -g folclor    # acervo de artistas
dor grade piata piață   # testa o motor de correção
```

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[audio,dev]"
dor doctor
```

O `[audio]` traz `edge-tts` (vozes neurais romenas Alina e Emil), `pygame` e,
para o Podcast Studio, `imageio-ffmpeg` + `mutagen` — nenhum deles exige
instalação no sistema. Sem o extra o app funciona, mas mudo.

## Arquitetura

**Conteúdo em JSON, validado por schema; progresso em SQLite.**
Atualizar o repositório nunca apaga progresso — os dados do usuário ficam em
`%LOCALAPPDATA%\dor`.

```
data/
  schema/          JSON Schema de cada tipo de conteúdo
  vocabulary/      palavras com quadro de formas completo
  sentences/       corpus de frases (alimenta cloze e podcast)
  grammar/         regras com drills DECLARATIVOS
  culture/
    slang/               argou, expressões, provérbios
    music/               fichas de artistas para o Lyrics Lab
    history/             linha do tempo, pelo efeito na língua
    daily/               cenas do dia a dia, com etiqueta
    minimal_pairs.json   contrastes auditivos
    books.json           biblioteca graduada
  bridges/         correspondências português ↔ romeno
dor/
  core/            models, loader, grading, srs, distractors, selection
  modes/           um arquivo por modo de estudo, todos devolvendo Exercise
  game/            xp, streaks, quests, achievements, session
  storage/         sqlite + migrations versionadas
  audio/           TTS com cascata de provedores, cache permanente e o studio
  ui/              tema, feedback, fichas e widgets do painel
```

### Três decisões que sustentam o resto

**1. Gramática generativa.** Uma regra não guarda exercícios — guarda um filtro:

```json
"drill": {
  "type": "transform",
  "query": { "pos": "noun", "gender": "f", "has_form": "forms.def_sg" },
  "from": "ro", "to": "forms.def_sg",
  "prompt_pt": "Coloque no definido:"
}
```

Uma regra + 80 substantivos femininos = 80 exercícios, sem escrever nenhum.
Cada palavra nova que entra no vocabulário gera exercícios sozinha.

**2. Registro em tudo.** Todo item carrega `formal | neutru | colocvial | argou | vulgar`,
com cor na interface. Aprender romeno por trap funciona muito bem — mas o app precisa
avisar quando algo não se fala com o chefe.

**3. Cache de áudio permanente.** Cada frase é sintetizada uma única vez na vida,
indexada por `sha1(texto|voz|ritmo)`. Depois das primeiras sessões o app roda offline
na prática — que é a defesa contra o provedor online sair do ar.

### Correção em três níveis

Rejeitar `piata` quando o aluno quis dizer `piață` faz desinstalar no terceiro dia;
aceitar sem comentar faz o diacrítico nunca ser aprendido. Por isso existe o meio:

```
$ dor grade piata piață
≈ quase (50%)   piață
   Faltou ț (t com vírgula embaixo — som de 'ts'), ă (a com breve).

$ dor grade piaţă piață
✓ certo   piață          # cedilha legada ş/ţ nunca é erro do aluno
```

A direção importa: acento faltando em **português** vale ponto cheio (`nao` = `não`),
porque não estamos ensinando ortografia do português. Em **romeno** o diacrítico é
parte do que se aprende, então vira `quase` com a correção nomeada.

Também são aceitos sem ressalva: caixa e pontuação, o `a` do infinitivo (`fi` = `a fi`),
artigos opcionais (`o livro` = `livro`) e sinônimos declarados no campo `accepts`.
Deslize de digitação só é perdoado em palavra longa — `masă` e `casă` distam um
caractere e são palavras distintas.

### Dizer a mesma coisa com outras palavras

`ce faci` está fichado como "como vai". Quem responde **"como está"** acertou — e um
vermelho ali ensina só a adivinhar a string da ficha:

```
$ dor grade "como está" "como vai" --lang pt
✓ certo   como vai
   também vale — na ficha: 'como vai'
```

Duas camadas, em `dor/core/synonyms.py`. A primeira derruba pronome solto, então
"como está você" = "como está" sem tabela nenhuma. A segunda são **grupos de ditos
intercambiáveis** — cumprimentar, agradecer, se despedir, pedir. Uma tradução que
não cabe em grupo nenhum, porque é específica daquela palavra ("angu" para
`mămăligă`), entra no campo `accepts_pt` do próprio item: ela vale como resposta,
mas não vira a forma canônica nem alternativa de múltipla escolha.

O afrouxamento tem um limite, e ele é testado: **"oi" continua errado para `ce faci`**,
que é pergunta e não cumprimento. O que garante isso é os grupos casarem por
pertencimento e nunca por corrente — dois ditos são equivalentes quando aparecem
JUNTOS em algum grupo, não porque existe um terceiro ligando os dois. Um dito
ambíguo como "e aí", que serve para os dois usos, fica fora de todos os grupos e
vale só como tradução literal de quem o lista.

### Contexto: a palavra não aparece do nada

Palavra sozinha na tela não ensina: o aluno lê `pâine`, lê "pão" e memoriza um par
de strings. Cada palavra tem um **símbolo** (`data/art/ilustracoes.json`, fora do
código, 178 de 178 cobertas), e ele aparece em três momentos, cada um com uma
razão diferente:

```
2/12  🥔  cartof   novo          ← na estreia, colado no enunciado
  traduza para o português
  >  batata
  ✓ certo   batata   +12 XP      ← e a ficha completa vem AQUI, depois da tentativa

5/12  inimă
  qual a tradução?
  >  4
  ❤️   ✓ certo   coração         ← em toda revisão, ao lado da correção
```

A ordem custou duas rodadas de feedback. A ficha inteira **antes** da pergunta
entregava a resposta e o exercício virava cópia; **nenhum** contexto fazia a palavra
aparecer do nada. O que fica antes é só o símbolo — ele dá o referente sem dar a
palavra — e a explicação vem depois, quando já existe uma tentativa em que grudar.

Durante a pergunta, **`?` mostra o símbolo e repete o áudio**. Essa dica é paga:
🥔 para `cartof` não é contexto, é a resposta. Continua valendo acerto, mas por
meio crédito e agendado como `HARD` — acerto com a resposta na tela não é
recuperação da memória, e tratar como se fosse faz a palavra sumir do radar sem
nunca ter sido lembrada sozinha.

A primeira versão disto era desenho ASCII e foi descartada: em quatro linhas de
barra e underline, `pão` e `batata` viram o mesmo borrão. O pictograma é legível na
hora e ainda alcança verbo e adjetivo, que rabisco de linha não alcançava —
`a se descurca` não tem desenho possível, mas tem 🤹.

### Agendamento

FSRS é o padrão. Mas um app de estudo que quebra porque um pacote mudou de API é
um app que se perde, então existe um **SM-2 em stdlib puro** que assume sozinho se
o `fsrs` não estiver instalado. Os dois gravam nas mesmas colunas.

O veredito da correção vira nota do agendador:

| Resposta | Nota | Efeito |
|---|---|---|
| errado | Again | volta logo |
| quase | Hard | sabia, tropeçou no acento |
| certo | Good | intervalo normal |
| certo em menos de 3 s | Easy | resposta automática, espaça mais |

**Nada fica só em memória.** O contador de sessão sobe a cada resposta, não no fim —
fechar o terminal no meio perde no máximo o que estava sendo digitado. O banco usa
WAL pelo mesmo motivo.

### Modos de estudo

Todo modo constrói um `Exercise` e não sabe mais nada — quem corrige, agenda, grava
e desenha é o mesmo código para todos. Adicionar um modo é escrever uma função
`build(...) -> Exercise`.

A dificuldade **sobe com a maturidade do item**, em vez de ser sorteada:

| Estágio | Modo | O que exige |
|---|---|---|
| nunca visto | tradução RO→PT | reconhecer, com áudio |
| visto pouco | múltipla escolha | distinguir de vizinhas |
| consolidando | lacuna na frase | usar em contexto |
| maduro | tradução PT→RO | produzir do zero |

Item marcado como *leech* volta ao reconhecimento — insistir na produção com uma
palavra que não gruda só acumula frustração.

**Distratores plausíveis.** Escolher entre `pâine` e `televizor` não ensina nada: a
resposta sai por eliminação. O ranqueamento pontua mesma classe, mesmo gênero, tags
em comum e semelhança ortográfica, e depois sorteia entre os melhores (senão o aluno
decora o layout da pergunta). Na prática:

```
a mânca   →  querer   morar   poder  *comer          todos verbos
bună ziua →  boa noite  sinto muito  saúde  *bom dia  todos saudações
casa      → *casă   masă   pâine   lapte             masă é o quase-gêmeo
```

**Gramática sem escrever questão.** As **31 regras** do acervo geram **751
exercícios** a partir do vocabulário. Cada palavra nova adicionada aumenta esse
número sozinha — `dor drill --list` mostra a contagem por regra.

### Gramática até B1

A1 cobre gênero, artigo definido e presente. A2 entra no que separa mesmo os
dois idiomas:

| Regra | Por que ela existe |
|---|---|
| **conjuntivo com `să`** | onde o português encadeia infinitivo ('quero comer'), o romeno exige `vreau **să** mănânc`. É a diferença estrutural nº 1 |
| futuro falado `o să` | `voi mânca` é jornal; na rua é `o să mănânc` — mesma divisão do nosso 'comerei' vs 'vou comer' |
| imperfeito vs perfeito composto | a divisão é idêntica à de 'comia' vs 'comi': quem escolhe certo em português acerta aqui |
| genitivo/dativo | o caso que o português trocou por 'de' e 'para' e nunca mais olhou |
| concordância do adjetivo | quatro formas, e o neutro cobrando o preço: masculino no singular, feminino no plural |
| pronomes átonos | o brasileiro fala 'eu vi ele'; o romeno não dá essa opção |
| `dumneavoastră` | tratar por 'tu' quem espera formal é erro social, não gramatical |

**Regra de teoria é uma escolha, não um buraco.** Pronome e ordem das palavras
não se geram por transformação do vocabulário — não há campo em `forms` que
produza `îmi place`. Essas regras vêm sem drill, e `dor drill --list` as marca
como `teoria` em vez de mostrar um `0` que parece conteúdo quebrado. Qualquer
regra, com drill ou sem, se lê inteira com `-t`:

```
$ dor drill g.pron.dativ -t
┌─ Pronomes átonos de dativo — îmi, îți, îi, ne, vă, le  A2 ──────────┐
│  O destinatário vira partícula: 'îmi place', 'îți dau', 'îi spun'.  │
│  em português                                                       │
│  É o nosso 'me/te/lhe' — que o brasileiro ainda usa em 'me dá'.     │
│  ⚠ a armadilha                                                      │
│  'A place' funciona ao contrário do nosso 'gostar': quem gosta vai  │
│  no dativo e a coisa é o sujeito. 'Îmi place cafeaua'.              │
└─────────────────────────────────────────────────────────────────────┘
```

O contraste vem logo depois da explicação porque é ele que fixa: ninguém aprende
o genitivo romeno decorando o genitivo romeno, e sim percebendo o que o
português faz no lugar dele. Há um teste que exige `contrast_pt` em **toda**
regra.

### Gamificação

```
XP = base(modo) × direção × crédito × velocidade × srs × combo
```

A fórmula premia o que é pedagogicamente caro, não o que é rápido de clicar:
produzir vale 1.3×, múltipla escolha vale metade de escrever, resposta em menos de
3 s ganha 1.2×, e recuperar uma palavra travada vale 1.5×. O **crédito vem do
veredito da F2**, então `quase` rende metade — errar o acento custa pontos, mas não
zera o esforço.

Nível por curva triangular (nível *n* custa `100 × n`), combo somando 10% por acerto
consecutivo até 2.0×.

**Streak com escudos.** Uma sequência que quebra por um único dia de viagem
desmotiva — o usuário desiste de recomeçar. A cada 7 dias o app guarda um escudo
(máx. 3), consumido automaticamente para cobrir uma falta. É perdão limitado, não
impunidade: três dias seguidos quebram mesmo. O dia é o **local**, não o UTC.

**Missões diárias** sorteadas de forma determinística pela data — meta que troca
sozinha não é meta. Uma delas é sempre uma missão-base que qualquer sessão avança,
senão o sorteio poderia dar três missões especializadas e você fecharia a sessão sem
mover nenhuma barra.

**13 conquistas**, metade premiando constância e metade as armadilhas específicas do
romeno para brasileiro — *Neutru nativ* (50 acertos de gênero), *Diacritic perfect*
(100 acertos escrevendo em romeno), *Revenire* (recuperar uma palavra travada).

### Boss Battle — `dor lupta`

O chefe é feito das **suas** palavras fracas, não de itens sorteados: uma luta
com vocabulário fácil não é desafio, é passatempo. Três vidas, só produção
(nada de múltipla escolha), e cada erro custa um coração.

```
3/12  querer   ♥♥
  traduza para o romeno
  > vroiam
  ✗ errado   →  a vrea

  sem vidas — a luta acabou
```

Sem histórico o comando se recusa a rodar e manda estudar antes — é a única
forma honesta de montar o chefe.

### A tela inicial

`dor` sozinho não despeja o `--help`. Quem digita o nome do app sem lembrar o
comando quer saber o que fazer **agora**: nível, streak, meta do dia e quantas
palavras estão vencendo.

Junto vem o cardápio inteiro das atividades, com selo **novo** no que ainda não
foi aberto nenhuma vez (`sessions.mode` no banco é quem sabe). A primeira versão
sugeria só `dor review` e escondia onze doze avos do app justamente de quem
estuda todo dia — que é quem já passou da tela de boas-vindas.

### Levar o material embora — `dor export-anki`

Sem dependência nova: um TSV com o cabeçalho que o Anki entende sozinho, mais
uma pasta de mídia com os MP3 do cache. Nada de `.apkg` — exigiria `genanki` e
um formato que muda entre versões do Anki.

O ponto não é migrar de app. É que conteúdo que só existe dentro de uma
ferramenta é conteúdo que se perde quando a ferramenta cansa.

### O painel

```bash
dor stats                 # tudo
dor stats --weeks 26      # meio ano de calendário
dor stats --compact       # só nível, missões e números
```

**Calendário de constância.** Uma barra de XP diz quanto você fez hoje; só o
calendário mostra o buraco de duas semanas em março. É a visão que a streak
esconde justamente ao zerar.

```
     mai jun       jul     ago
 seg ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
 qua ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
 sex ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
     menos ■■■■■ mais   (verde forte = 120 XP, a meta do dia)
```

A cor mede o dia **contra a meta**, não contra o seu melhor dia — se fosse
relativa ao pico, baixar o ritmo repintaria o passado inteiro de verde.

**Onde você tropeça.** O painel cruza o histórico bruto com o acervo e responde
três perguntas que a acurácia geral esconde:

| Recorte | Pergunta que responde |
|---|---|
| domínio por tema | vou mal em quê? (o pior tema vem primeiro) |
| palavras fracas | quais palavras estão me custando caro? |
| gramática por regra | qual regra ainda não entrou? |
| por modo de estudo | escrevo pior do que reconheço? |
| hora do dia | quando eu acerto mais? |

O ranking usa **crédito médio**, não acurácia: um `quase` vale meio acerto, do
mesmo jeito que na correção — senão errar o acento ficaria indistinguível de
não saber a palavra. Palavra com menos de 3 respostas não entra na lista de
fracas, e o "melhor horário" exige 10 revisões na faixa: sem piso de amostra,
uma resposta certa às 4h da manhã viraria conselho de estudo.

### Modos de áudio

| Comando | O que treina |
|---|---|
| `dor listen --mode ditado` | ouvir e **escrever em romeno** — ortografia dos diacríticos |
| `dor listen --mode escuta` | ouvir e **traduzir** — compreensão, sem ver a grafia |
| `dor pairs` | **discriminação**: qual das duas palavras foi tocada |
| `dor shadow` | **produção**: devagar → sua vez → velocidade normal |

`[r]` repete o áudio quantas vezes você quiser. O tempo das repetições entra na
latência, então repetir custa o bônus de velocidade — mas nunca custa acerto.

O áudio de toda a sessão é **sintetizado antes de começar**, com barra de progresso.
Sem isso cada pergunta pagaria a latência da rede na frente do usuário.

**15 pares mínimos** com contrastes que o ouvido brasileiro não separa sozinho —
`ș/s`, `ț/t`, `ă/a` e o temido `â`. Há um teste que rejeita par trivial: todo par ou
fica idêntico ao remover os diacríticos, ou envolve `â`/`î`, a vogal que o português
não tem.

```
pește / peste     peixe / sobre
mușca / musca     morder / a mosca
deșert / desert   deserto / sobremesa
față / fată       rosto / menina
râu / rău         rio / mau
casă / casa       uma casa / a casa   ← gramática disfarçada de fonética
```

**Aqui o perdão do acento é desligado.** Em `pește`/`peste` a diferença é só um
diacrítico, então a regra geral da F2 daria `quase` e meio ponto por escolher a
palavra errada — desmontando o exercício, já que distinguir as duas *é* a atividade.
Os pares mínimos ligam `strict_diacritics` e o erro vale zero. O rigor é local: em
qualquer outro modo, `piata` continua valendo `quase`.

### Podcast Studio

O estudo no terminal exige as mãos e os olhos. O trajeto, a academia e a louça
não — e é onde estão as horas sobrando. `dor podcast` transforma o vocabulário
em episódios que rodam em qualquer player.

```bash
dor podcast --theme bebida --items 12         # drill: pausa para responder
dor podcast --mode passive --minutes 20       # só romeno, para ouvir de fundo
dor podcast --mode sleep --deck a1_saluturi   # lento e repetido
dor podcast --theme casa --dry-run            # mostra o roteiro sem sintetizar
```

| Modo | Estrutura | Para quando |
|---|---|---|
| `drill` | RO → **silêncio** → PT → RO devagar (voz trocada) | atenção disponível |
| `passive` | só romeno, vozes alternando | lavando louça |
| `sleep` | tudo lento, repetido, pausas longas | antes de dormir |

**A pausa vem antes da tradução, não depois.** É a janela em que você tenta
lembrar sozinho; entregar o português primeiro transforma o episódio em
audiolivro. A confirmação repete a palavra em **outro timbre e mais devagar** —
alternar a voz impede o ouvido de decorar a gravação em vez da palavra.

Cada episódio sai com **transcrição em Markdown**, **playlist M3U** e **tags ID3**,
para aparecer com nome decente no player. `--dry-run` imprime o roteiro inteiro
antes de gastar minutos sintetizando — o planejamento é código puro, sem rede
nem disco, o que também o torna testável de ponta a ponta.

`dor export-audio` faz o outro formato: um MP3 por palavra mais a playlist,
**copiados do cache** em vez de sintetizados de novo — o mesmo áudio serve à
sessão de estudo e ao arquivo offline.

> **Sem pydub, sem instalar ffmpeg.** O `pydub` importa `audioop`, removido do
> Python 3.13 pela PEP 594 — ele simplesmente não roda aqui. O app fala direto
> com o ffmpeg, que vem por `pip` via `imageio-ffmpeg`, e lê duração e tags com
> `mutagen`. A concatenação passa por um `filter_complex_script` em arquivo:
> com 100 falas o filtro estoura o limite de linha de comando do Windows.

## Cognate Bridge — derivar em vez de decorar

A tese do projeto virada em regra operacional. Português e romeno saíram do
mesmo latim e mudaram de formas **diferentes, mas regulares**:

| ponte | português | romeno | exemplo |
|---|---|---|---|
| -CT- | -it- | **-pt-** | noite → *noapte*, leite → *lapte* |
| rotacismo | -l- | **-r-** | céu → *cer*, sal → *sare* |
| QUA | qua- | **pa-** | água → *apă*, quatro → *patru* |
| -GN- | -nh- | **-mn-** | lenho → *lemn*, cunhado → *cumnat* |
| sufixo | -ção | **-ție** | informação → *informație* |
| sufixo | -dade | **-tate** | liberdade → *libertate* |
| sufixo | -ável | **-abil** | possível → *posibil* |

São 16 pontes. O exercício não pergunta "o que significa" — pergunta **aplique
a regra**: quem sabe que -ção vira -ție não precisa nunca ter visto
`informație` para acertar.

**As armadilhas são exercício também.** Uma ponte sem exceção conhecida vira
excesso de confiança, e é mais barato descobrir que *cidade* não vira `citate`
(é `oraș`, do húngaro) num drill do que numa conversa. Nos exercícios a regra
vem antes da exceção; nas fichas, a armadilha nunca fica escondida.

`dor punte -t` sem argumento roda a sessão **misturada** entre pontes: uma de
cada vez ensina o padrão, misturar ensina a *escolher* o padrão — que é o que a
vida real cobra.

E a ponte mais importante é a que **não existe**: o romeno não tem sufixo de
advérbio, usa o adjetivo cru (`vorbește rapid`). Inventar um `-ment` romeno é o
erro que mais denuncia falante de língua latina.

## Cultura — o país junto com o idioma

Quatro fases inteiras existem porque vocabulário sem contexto não gruda, e
porque o que faz alguém passar por estrangeiro raramente é a gramática.

### Vida cotidiana — `dor zi`

Oito cenas: café, rua, táxi, feira, restaurante, casa de alguém, telefone,
farmácia. Cada uma traz o diálogo com os dois lados, as fórmulas que valem
decorar, o **contraste entre o que o livro ensina e o que se fala**, e a
etiqueta.

| o livro ensina | na rua |
|---|---|
| `Aș dori o cafea.` | `O cafea, vă rog.` |
| `Mulțumesc foarte mult.` | `Mersi!` |
| `Am o durere de cap.` | `Mă doare capul.` |
| `Ha ha ha` | `:))))` |

O treino da cena é **sempre de produção**, PT→RO. Reconhecer `Cât costă?` não
adianta nada no balcão da padaria — na hora, quem tem de produzir a frase é
você. E só as **suas** falas viram exercício: não é preciso saber produzir a
fala do garçom.

A etiqueta fica em destaque no fim da ficha porque é o que de fato entrega
alguém de fora — quem chega com buquê de número par acertou a gramática inteira
e errou a única coisa que vai ser lembrada. (Flores em número par são de
enterro. Sapato sai na porta. `Bine ai venit` pede `bine te-am găsit`.)

### Lyrics Lab — `dor lyrics`

O acervo tem duas metades. **Folclore, colinde e poesia do século XIX** são
domínio público, então os versos aparecem na tela e viram exercício: Miorița,
*Hora Unirii*, Eminescu musicado, *O, ce veste minunată*. **Trap e hip-hop**
(Subcarpați, B.U.G. Mafia, Paraziții, Șatra B.E.N.Z.) entram como ficha,
glossário e link — nunca com letra.

Dois tipos de exercício por faixa: lacuna no verso, com a tradução como apoio,
e glossário nas duas direções. Os versos vêm **antes** do glossário: o verso dá
o contexto em que a palavra vive; na ordem inversa o exercício vira lista.

### História — `dor istorie`

17 eventos, do substrato dácio à diáspora pós-2007. O critério de entrada não é
importância histórica: é **efeito linguístico**. Todo evento carrega um campo
obrigatório dizendo o que fez com a língua, e um teste recusa quem não tiver.

Por isso a ficha inverte o peso de um livro de história: *o que aconteceu* sai
em cinza, *o que isso fez com a língua* em branco.

```
$ dor istorie cafea
→ A época fanariota (1711–1821)
  cafea, ciorbă, iaurt, musafir, chef, dușman   turco
  ieftin, a plictisi                            grego
```

O evento sobre a **liga linguística balcânica** aponta para as regras de
gramática que ele explica: o artigo grudado no fim e o `să` que substituiu o
infinitivo não são latim torto — vieram do convívio com o albanês, o búlgaro e
o grego. Saber disso transforma decoreba em explicação.

### Biblioteca — `dor livros`

15 obras ordenadas pela dificuldade **real para quem fala português**, não por
importância literária: começa nos contos do Creangă e termina em Cărtărescu.
Toda ficha traz *por que ler* e, obrigatoriamente, *o que esperar* — o primeiro
vende o livro, o segundo evita que ele seja abandonado na página 20 achando que
o problema é você.

### A trava de direito autoral

Música e literatura têm o mesmo problema — o material bom quase sempre é de
alguém — então têm a mesma trava, em `dor/core/quoting.py`:

> O app guarda ficha, glossário e link para qualquer obra, mas só reproduz
> **texto** quando ele está em domínio público.

A checagem é `public_domain is True`: `"true"` em texto, `1` ou `"sim"` são
quase-verdades que não valem como autorização. E a marca no catálogo não
autoriza sozinha — quem autoriza é a marca no próprio trecho, porque é ele que
vai para a tela. Autor vivo entra com ficha e onde comprar; o texto dele, não.
Obra protegida continua rendendo estudo pelo glossário, que é livre.

## O acervo pessoal — `dor versuri`, `dor jurnal`, `dor atualizar`

A trava acima protege o que o projeto **publica**. Mas estudar rap contemporâneo
só pelo glossário é estudar pela metade, e o material que mais ensina — a música
que você ouve, a notícia desta semana — quase sempre é de alguém.

A saída não foi afrouxar a trava do repositório: foi criar um **segundo acervo**,
em `%LOCALAPPDATA%\dor\conteudo`, do lado do progresso e fora do git. O que entra
ali é seu e fica com você. `data/` continua publicável; o acervo pessoal, não
viaja.

```
%LOCALAPPDATA%\dor\conteudo\
  inbox\        rascunho — não vira exercício até você importar
  versuri\      música, uma parte por estrofe
  jurnal\       notícia da semana
```

### O ciclo da semana

```bash
dor atualizar --modelo jurnal      # esqueleto do arquivo, para preencher
dor atualizar --letra letra.txt --titulo "..." --artista "..."
dor atualizar                      # promove a caixa de entrada e mostra o acervo
dor versuri                        # o que tem para estudar
dor jurnal 2026w34.energie         # ficha parte por parte + sessão de exercícios
```

`dor atualizar` é o único caminho da caixa de entrada para o acervo, e ele valida
contra `lote.schema.json` antes de mover: lote torto fica onde está e diz por quê.
Um arquivo inválido nunca esconde os válidos — o `load_local` acumula problemas em
vez de abortar, porque este material é editado à mão toda semana.

O comando **não vai à internet**. Quem escolhe a faixa e a notícia é uma pessoa, e
o texto da música sai de um `.txt` que você colou: `--letra` quebra por estrofe,
monta uma parte para cada uma e deixa tradução, comentário e glossário em branco —
que é exatamente o trabalho de anotação da semana.

### Por que "parte por parte"

Glossário solto no fim da ficha não ensina música. Cada pedaço aparece com o
verso, a tradução embaixo, o que está acontecendo ali — gíria, elisão, referência
— e só então as palavras **daquele** pedaço, para que a explicação fique ao lado
do que ela explica e não trinta linhas abaixo.

Do pedaço saem dois tipos de exercício: cada entrada de glossário vira tradução, e
o `cloze_answer` apaga do verso exatamente a palavra que a explicação acabou de
ensinar. Glossário primeiro, lacuna depois — cobrar produção antes do primeiro
reconhecimento é pedir para errar à toa.

O rótulo de sessão é o próprio tipo (`versuri`, `jurnal`), e não um `MODE` único.
É o que permite a tela inicial dizer "você nunca abriu o jornal" sem confundir com
"você nunca abriu a música".

## Conteúdo semente

| Tipo | Qtd. |
|---|---|
| Vocabulário | 178 |
| Frases | 56 |
| Regras de gramática | 31 (A1 → B1) |
| Exercícios de gramática gerados | 751 |
| Gíria / expressões / provérbios | 24 |
| Pares mínimos | 15 |
| Artistas / faixas | 11 / 13 |
| Eventos históricos | 17 |
| Livros | 15 |
| Cenas do dia a dia | 8 |
| Pontes de cognato | 16 |

Cada palavra traz, quando cabe: cognato em português, alerta de falso amigo
(`carte` = livro, não carta) e camada etimológica — porque `mișto`, `nasol` e `baftă`
vêm do **romani**, e `da` e `a iubi` vêm do **eslavo**. Marcar onde a intuição latina
*não* ajuda economiza frustração.

## Direitos autorais

O acervo guarda **fichas, glossário e links** para streaming e livrarias. Letra
integral, texto de livro protegido e áudio de obra alheia nunca são armazenados.
Trechos existem apenas para material de domínio público — no máximo 4 versos ou
6 linhas — e a regra vive em `dor/core/quoting.py`, com testes que a exercem
pelos dois lados. Veja **A trava de direito autoral**, acima.

## Desenvolvimento

```bash
pytest          # 408 testes
ruff check .
```

Os testes validam o conteúdo, não só o código: substantivo sem gênero, verbo com
número errado de pessoas, drill que não casa com nenhum item, referência quebrada
entre frase e vocabulário — tudo falha antes de chegar numa sessão de estudo.

Dois deles varrem o acervo inteiro contra o motor de correção: toda palavra deve
se autoavaliar como certa, e nenhuma pode virar `errado` quando digitada sem
diacríticos.

## O que vem depois

**Correção por voz** é a maior lacuna funcional que sobrou: o app fala, mas não
ouve — `dor shadow` pede que você repita e confia na sua palavra. Whisper local
resolveria, e ficou de fora de propósito: exige dependência pesada e download de
um modelo grande, o que contraria a regra do projeto de rodar sem instalar nada
no sistema.

Fora isso, o caminho é conteúdo — **B2 e C1**, mais frases, mais decks
temáticos. O motor não precisa de nada novo para absorvê-los: as 31 regras de
gramática passaram de 243 para 751 exercícios só porque o vocabulário cresceu.
