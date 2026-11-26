# dor

**Guia de uso** — — romeno para quem fala português

Dor é a palavra romena para saudade — o único par perfeito entre os dois idiomas.

## 1. Antes de tudo

O dor roda no terminal. Toda vez que você abrir uma janela nova, faça estes dois passos antes de qualquer comando:

```
cd caminho/para/dor
.venv\Scripts\activate
```

A partir daí, o comando dor funciona. Se você fechar o terminal e abrir outro, repita — é o que ativa o ambiente Python do projeto.

Para conferir se está tudo no lugar: `dor doctor`

Ele mostra o Python em uso, se o áudio (TTS) está ativo, o tamanho do acervo e um teste de diacríticos. Se você enxergar ă â î ș ț corretamente na tela, seu terminal está preparado para o romeno.

## 2. Sua primeira sessão

```
Digite dor sozinho. Ele mostra o que fazer agora — na primeira vez, sugere por onde começar.
```

Depois, a sessão de estudo:

```
dor review
```

Como funciona, na prática:

- Aparece uma palavra em romeno e o áudio toca sozinho.

- Você digita a tradução em português e aperta Enter.

- O app corrige, mostra os pontos ganhos e passa para a próxima.

Três coisas que ajudam desde o primeiro dia:

- Não trave por causa dos acentos. Escrever piata em vez de piață conta como “quase” — vale meio ponto, e o app diz exatamente qual acento faltou.

- Enter vazio pula a palavra sem penalidade.

- Ctrl+C encerra a qualquer momento e tudo que você já respondeu está salvo. Não existe “sair sem salvar”.

A dificuldade sobe sozinha conforme a palavra amadurece: você começa só reconhecendo, depois escolhe entre alternativas, depois completa a lacuna numa frase e, por fim, escreve em romeno do zero. Não é preciso configurar nada.

## 3. A rotina que eu sugiro

Constância importa mais que duração. Quinze minutos por dia rendem muito mais que duas horas no domingo — o agendador do app é construído em cima disso.

Depois de uma semana de uso, o dor lupta passa a fazer sentido: ele monta a luta com as palavras que VOCÊ errou, então precisa do seu histórico para existir.

## 4. Para os ouvidos, longe do computador

Isto rende muito no começo, quando você ainda não produz nada:

```
dor podcast --theme casa --minutes 15
```

Gera um MP3 com transcrição e playlist na pasta de exportação (%LOCALAPPDATA%\dor\exports). Passe para o celular e ouça no trajeto.

A pausa vem ANTES da tradução de propósito: é a janela em que você tenta lembrar sozinho. Se o português viesse antes, o episódio viraria audiolivro.

```
Para ver o roteiro sem gastar tempo sintetizando: dor podcast --theme casa --dry-run
```

## 5. Como ler o painel

```
dor stats
```

É o comando que responde “como eu estou indo?”. Ele imprime vários blocos, de cima para baixo. Abaixo, o que cada um significa.

### 5.1. O cabeçalho: nível, streak e meta

```
nível 3  ██████░░░░░░░░░░░░  180/300   ·   680 XP no total

streak 5 dia(s)  (recorde 11)   ❄ 1 escudo(s)

meta de hoje ████████████░░░░░░  75/120 XP
```

- Nível e XP — o XP premia o que é pedagogicamente caro, não o que é rápido de clicar: escrever em romeno vale mais que múltipla escolha, e recuperar uma palavra travada vale 1,5×.

- Streak — dias seguidos de estudo. A cada 7 dias você ganha um escudo (❄, máximo 3), consumido automaticamente para cobrir uma falta. É perdão limitado: três dias seguidos quebram mesmo. Se a sequência estiver em risco, aparece um aviso.

- Meta de hoje — o padrão é 120 XP (uns 15 minutos). Se for demais para a sua rotina, diminua: meta que você não bate desmotiva mais que meta pequena.

### 5.2. Missões do dia

```
missões de hoje
  · ███░░░░░░░░░  6/20  Responda 20 revisões  +40
  ✔ ████████████  5/5   Conheça 5 palavras novas  +35
```

Três missões sorteadas pela data — sempre as mesmas se você abrir dez vezes no mesmo dia, porque meta que muda sozinha não é meta. Uma delas é sempre uma missão-base que qualquer sessão avança.

### 5.3. Constância — o calendário

```
     mai jun       jul     ago
 seg ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
 qua ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
 sex ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■ ■
     menos ■■■■■ mais   (verde forte = 120 XP, a meta do dia)
```

Um quadrado por dia, uma coluna por semana. Cinza é dia em branco; quanto mais verde, mais perto (ou além) da meta.

A cor mede o dia contra a SUA META, não contra o seu melhor dia. Se fosse relativa ao pico, baixar o ritmo repintaria o passado inteiro de verde — o gráfico mentiria para agradar.

```
Para ver meio ano de uma vez: dor stats --weeks 26
```

### 5.4. Os números

### 5.5. Onde você está tropeçando

Esta é a parte que a acurácia geral esconde. São quatro recortes:

O ranking usa crédito médio, não acurácia: um “quase” vale meio acerto, do mesmo jeito que na correção — senão errar o acento ficaria indistinguível de não saber a palavra. E há piso de amostra: palavra com menos de 3 respostas não entra na lista de fracas.

### 5.6. Quando você estuda

```
  0h     ▄▄  ▄      ▄▃█▇▃   23h
  seu melhor horário é por volta das 21h — 84% de acerto em 240 revisões
```

Volume por hora do dia e a faixa em que você mais acerta. Exige pelo menos 10 revisões na faixa para virar conselho — sem isso, um acerto solitário às 4h da manhã viraria recomendação.

### 5.7. Próximos 7 dias e conquistas

A previsão de carga mostra quantas revisões vencem em cada um dos próximos sete dias — serve para você não acordar com 300 pendências sem aviso. Abaixo dela, as conquistas desbloqueadas (são 13 no total; metade premia constância, metade as armadilhas específicas do romeno para brasileiro).

```
Se quiser só o essencial, sem os recortes de diagnóstico: dor stats --compact
```

## 6. Todos os comandos

27 comandos, agrupados pelo que você quer fazer. As opções curtas (-n, -t) são atalhos das longas.

### Estudar

O núcleo do app. Se você só usar esta seção, já funciona.

```
dor review
```

Sessão de estudo. O modo sobe de dificuldade conforme o item amadurece.

```
--limit, -n  Quantos itens na sessão
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--deck, -d  filtra por deck de vocabulário
```

```
--pos, -p  filtra por classe (noun, verb, adj…)
```

```
--tag, -t  filtra por tema
```

```
--mode, -m  traducao | escolha | lacuna (padrão: mistura)
```

```
--silent, -s  Sem áudio
```

```
dor drill <rule_id>
```

Treino de gramática, com exercícios gerados a partir das regras.

```
<rule_id>  ID da regra (ex.: g.gen.neutru)
```

```
--limit, -n  quantos itens na sessão
```

```
--list  Só listar as regras
```

```
--level, -l  Filtra a lista por nível
```

```
--teoria, -t  Só ler a regra, sem treinar
```

```
--silent, -s  sem áudio
```

```
dor listen
```

Sessão de escuta: ditado (escreve em romeno) e compreensão (traduz).

```
--limit, -n  quantos itens na sessão
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--deck, -d  filtra por deck de vocabulário
```

```
--mode, -m  ditado | escuta | misto
```

```
--frases  Ditar frases, não palavras
```

```
dor pairs
```

Pares mínimos: ouça e diga qual das duas palavras foi.

```
--limit, -n  quantos itens na sessão
```

```
--contrast, -c  Filtra por contraste, ex.: "ț"
```

```
--list  Só listar os pares
```

```
dor shadow
```

Shadowing: ouça devagar, repita em voz alta, ouça na velocidade normal.

```
--limit, -n  quantos itens na sessão
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--rate  Ritmo da 1ª passada
```

```
dor lupta
```

Boss Battle: só as palavras que te derrubam, com vidas contadas.

```
--limit, -n  Tamanho da luta
```

```
--vidas, -v
```

```
--silent, -s  sem áudio
```

```
dor punte <ref>
```

Cognate Bridge: as correspondências que transformam português em romeno.

```
<ref>  ID ou padrão (ex.: cao, ct)
```

```
--tipo, -k  sunet | sufix
```

```
--treinar, -t  Treinar a ponte
```

```
--limit, -n  quantos itens na sessão
```

```
--silent, -s  sem áudio
```

### Acompanhar o progresso

Ver onde você está e proteger o que já fez.

```
dor stats
```

Painel de progresso: nível, calendário, pontos fracos e carga futura.

```
--weeks, -w  Semanas no calendário
```

```
--compact, -c  Só o essencial
```

```
dor backup
```

Salva ou restaura o progresso.

```
--restaurar, -r  Arquivo .db a restaurar
```

```
--list  Listar os backups existentes
```

```
--out, -o  arquivo ou pasta de saída
```

```
--sim, -y  Não perguntar ao restaurar
```

```
dor undo
```

Desfaz a última resposta e reagenda o item.

```
dor destravar <palavra>
```

Tira a marca de 'travado' de um item que voltou a entrar.

```
<palavra>  Palavra ou ID; vazio = todas
```

```
dor settings
```

Mostra ou altera suas preferências.

```
--meta  XP por dia
```

```
--voz  alina | emil
```

```
--ritmo  ex.: -20%, +0%
```

```
--autoplay
```

### Cultura

Para os momentos de curiosidade — não é “estudo”, é passeio.

```
dor zi <ref>
```

Vida cotidiana: o diálogo, as fórmulas, a rua e a etiqueta.

```
<ref>  ID ou parte do título (ex.: cafenea)
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--treinar, -t  Treinar as fórmulas
```

```
--ouvir, -o  Tocar o diálogo inteiro
```

```
--silent, -s  sem áudio
```

```
dor lyrics <track_ref>
```

Lyrics Lab: estuda uma faixa pelo glossário e pelos versos citáveis.

```
<track_ref>  ID ou parte do título (ex.: miorita)
```

```
--genre, -g  filtra por gênero musical
```

```
--ler, -r  Só a ficha, sem treinar
```

```
--limit, -n  quantos itens na sessão
```

```
--silent, -s  sem áudio
```

```
dor istorie <ref>
```

A história da Romênia contada pelo que ela fez com a língua.

```
<ref>  ID, parte do título ou uma palavra (ex.: cafea)
```

```
--era, -e  dacia, roma, fanariot...
```

```
--palavras, -p  Só as camadas de vocabulário
```

```
dor livros <ref>
```

Biblioteca graduada: o que ler em romeno, e em que ordem.

```
<ref>  ID, título ou autor
```

```
--level, -l  A2, B1, B2, C1, C2
```

```
--livre  Só o que está em domínio público
```

```
--treinar, -t  Estudar o glossário
```

```
--silent, -s  sem áudio
```

```
dor slang
```

Lista gíria, expressões e provérbios com o espelho em português.

```
--register, -r  filtra por registro (formal, colocvial, argou…)
```

```
--kind, -k  cuvant, expresie, proverb
```

```
dor music
```

Lista os artistas do acervo cultural.

```
--genre, -g  trap, folclor, fusion...
```

### Áudio e exportação

Levar o material para fora do terminal.

```
dor podcast
```

Gera um episódio MP3 para ouvir offline, com transcrição e tags ID3.

```
--mode, -m  drill | passive | sleep
```

```
--theme, -t  Tag do vocabulário
```

```
--deck, -d  filtra por deck de vocabulário
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--minutes  Duração alvo
```

```
--items, -n  Nº de itens
```

```
--pause  Pausa para responder, em ms
```

```
--number  Nº do episódio
```

```
--out, -o  Arquivo de saída
```

```
--dry-run  Só mostrar o roteiro
```

```
dor export-audio
```

Exporta um MP3 por palavra (ou frase) mais uma playlist, para ouvir offline.

```
--deck, -d  filtra por deck de vocabulário
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--theme, -t  filtra por tema
```

```
--frases  Exportar frases, não palavras
```

```
--voice, -v  alina | emil
```

```
--out, -o  Pasta de destino
```

```
dor export-anki
```

Exporta o vocabulário para o Anki (TSV + pasta de mídia).

```
--deck, -d  filtra por deck de vocabulário
```

```
--level, -l  filtra por nível (A1, A2, B1…)
```

```
--theme, -t  filtra por tema
```

```
--audio  Incluir os MP3 do cache
```

```
--sintetizar  Gerar o áudio que faltar (precisa de rede)
```

```
--out, -o  arquivo ou pasta de saída
```

```
dor say <text>
```

Sintetiza e toca um texto em romeno (fica em cache para sempre).

```
<text>  Texto em romeno
```

```
--voice, -v  alina | emil | <id edge-tts>
```

```
--rate  ex.: "-20%"
```

### Consulta e manutenção

Procurar uma palavra, conferir o ambiente.

```
dor list
```

Lista e filtra o vocabulário carregado.

```
--level, -l  A1, A2, B1...
```

```
--pos, -p  noun, verb, adj, expr...
```

```
--gender, -g  m, f, n
```

```
--register, -r  filtra por registro (formal, colocvial, argou…)
```

```
--tag, -t  filtra por tema
```

```
--deck, -d  filtra por deck de vocabulário
```

```
--limit, -n  quantos itens na sessão
```

```
dor show <word>
```

Mostra a ficha completa de uma palavra e toca a pronúncia.

```
<word>  Palavra em romeno ou ID (ro.casa)
```

```
--silent, -s  Não tocar o áudio
```

```
dor grade <resposta> <alvo>
```

Testa o motor de correção contra uma resposta — útil para calibrar conteúdo.

```
<resposta>  O que o aluno digitou
```

```
<alvo>  Uma ou mais respostas aceitas
```

```
--lang, -l  Idioma da resposta: ro ou pt
```

```
dor doctor
```

Diagnostica o ambiente: Python, conteúdo, provedores de TTS e cache.

```
dor validate
```

Valida todos os JSON contra os schemas e checa referências cruzadas.

## 7. Situações comuns

### Errei sem querer (apertei Enter cedo, digitei torto)

```
dor undo
```

Apaga a última resposta e recalcula o agendamento daquela palavra.

### Uma palavra ficou marcada como “travada” mas eu já aprendi

```
dor destravar casă
dor destravar          # todas de uma vez
```

A marca é um diagnóstico do passado, não uma sentença. Enquanto ela existe, o app insiste em te mostrar a palavra no modo mais fácil.

### Quero proteger meu progresso

```
dor backup
dor backup --list
dor backup --restaurar <arquivo>
```

Restaurar salva automaticamente o progresso que está sendo substituído antes de sobrescrever — dá para voltar atrás.

### A meta diária está grande (ou pequena) demais

```
dor settings --meta 60
dor settings
```

### Quero estudar sem áudio (no escritório, sem fone)

Quase todos os comandos de estudo aceitam -s:

```
dor review -s
```

### Não tem som nenhum

```
Rode dor doctor e olhe a linha TTS. Se estiver vazia, instale o extra de áudio:
```

```
pip install -e ".[audio]"
```

O primeiro áudio de cada palavra precisa de internet. Depois disso fica em cache para sempre e o app roda offline na prática.

### Quero focar num assunto específico

```
dor review --tag comida
dor review --deck a2_oras
dor review --level A1
dor list --pos verb        # ver o que existe
```

## 8. Uma última coisa

O app foi construído em cima de uma tese: o atalho de um brasileiro para o romeno é o latim que sobrou nos dois. Metade do vocabulário você já sabe sem saber — noite/noapte, leite/lapte, informação/informație.

```
Se um dia bater desânimo, rode dor punte e olhe o tamanho do atalho que você já tem.
```

Baftă!  —  boa sorte, em romeno