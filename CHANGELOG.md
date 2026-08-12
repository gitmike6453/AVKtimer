# Changelog / Relatório de limpeza e correções

Ponto de partida: pasta de desenvolvimento `TIMER/` (não alterada, mantida intacta).
Este repositório nasce a partir de `TIMER WIN.py`, identificado como a versão mais
recente e completa (já unifica Windows e Mac no mesmo ficheiro via deteção de SO em
runtime — `time.py` e `time NOVO.py` eram rascunhos anteriores só-Windows).

## Bugs corrigidos

1. **Rota `/api/reset` duplicada** — havia duas definições Flask para a mesma rota
   (`api_reset_timer_direto` e `api_comando_reset_exclusivo_companion`). A segunda
   nunca era alcançada (o Flask/Werkzeug fica sempre com a primeira registada),
   ficando como código morto. Consolidado numa única rota.
2. **Painel de botões "toggles" duplicado** — o bloco inteiro que cria os botões
   "MODO NEGATIVO", "MODO RELÓGIO", "ECRÃ LIGAR/DESLIGAR", "PISCAR", "SOM" e "PARAR
   SOM" estava copiado duas vezes, gerando widgets Tkinter órfãos na mesma posição da
   grelha (a segunda cópia tapava sempre a primeira). Removida a cópia redundante.
3. **Botão "RESET" (🔄) forçava sempre 15 minutos** — `forcar_reset_timer_via_botao`
   substituía `tempo_inicial_memoria` por um valor fixo de 900s a cada clique,
   corrompendo silenciosamente a memória do tempo configurado pelo operador (mesmo
   os outros botões RESET/REINICIAR passavam a usar 15 min depois disso). Corrigido
   para respeitar sempre o tempo que o operador configurou.
4. **Sons customizados gravados em pasta não-gravável** — o botão "BUSCAR" gravava
   o `.mp3`/`.wav` na pasta de arranque do processo (`os.getcwd()`), que numa
   instalação em `Program Files` normalmente não tem permissão de escrita para o
   utilizador; a falha ficava silenciosa (`except: pass`) e o alarme voltava sempre
   ao beep do sistema. Passa agora a usar `%APPDATA%\AVKtimer` (Windows) /
   `~/Library/Application Support/AVKtimer` (macOS).
5. **Ícone/sons em falta no executável empacotado** — o `.spec` do PyInstaller não
   incluía `app.ico`/`app.icns` nem os `.mp3` de alarme nos `datas`; depois de
   instalado, o ícone da barra de tarefas e os alarmes "Custom" podiam falhar
   silenciosamente por não existirem dentro do pacote onefile. Corrigido no novo
   `packaging/windows/AVKtimer.spec`.
6. Limpeza de código morto redundante: `SISTEMA_MAC` estava definido duas vezes,
   havia dois blocos a chamar `SetCurrentProcessExplicitAppUserModelID` com IDs
   diferentes (o segundo sempre vencia, o primeiro era inútil) e `import ctypes`
   duplicado.

## Lacuna na integração Companion

O módulo dedicado (`companion-plugins/main.js`) só expunha 7 das ~20 rotas que a
app já disponibiliza (faltavam Reset, Ligar/Desligar Ecrã, ajustes de tempo,
Atualizar, Piscar, tamanho de fonte, definir tempo exato). Foi expandido para
cobrir todas as ações documentadas, e passou a ler `/status` periodicamente para
publicar variáveis (`tempo`, `estado`, `mensagem`, `modo_web`) utilizáveis no texto
dos botões do Stream Deck. `package.json` também passou a declarar a dependência
`@companion-module/base` (antes em falta).

## Reestruturação / limpeza

- `TIMER WIN.py` → `avktimer.py` (nome neutro, já que corre em Win e Mac).
- `templates/`, `static/`, `app.ico`, `app.icns`, sons por omissão → mantidos.
- Removidos por não estarem referenciados em lado nenhum do código
  (`index.html` é autocontido, com CSS/JS inline): `templates/script`,
  `templates/script.js`, `templates/style.css`, `templates/style.html`,
  `templates/gerar_projeto.py` (ficheiro vazio, 0 bytes).
- Removidos ficheiros de build antigos/duplicados, mantendo só a versão final:
  `AVKtimer_v1.2.spec`, `AVKtimer_v1.3.spec`, `TIMER WIN.spec`, `time.spec` (a favor
  de `packaging/windows/AVKtimer.spec`, que corresponde ao instalador `.iss` mais
  recente v1.7); `avk.wxs` (WiX, referenciava `AVKtimer_v1.3.exe`, obsoleto e
  substituído pelo Inno Setup).
- Removidos os rascunhos de código anteriores `time.py`, `time NOVO.py`,
  `time NOVO Mac.py` — funcionalidade totalmente coberta por `avktimer.py`.
- Removidas pastas geradas/ambiente que não pertencem ao controlo de versões:
  `.venv/` (102 MB), `build/` (49 MB), `dist/` (37 MB), `Output/` (122 MB — instaladores
  antigos, serão recriados pelo CI), `.idea/`, `.wix/`.
- Removido `cloudflared.exe` / `cloudflared .exe` (binário de terceiros duplicado,
  65 MB cada, não é código do projeto) e o ficheiro `Novo Documento de Texto.txt`
  que continha um **token de túnel Cloudflare em texto simples** — não publicado por
  ser uma credencial; recomenda-se gerar um novo token caso ainda uses esse túnel.
- `meu icon.icns` removido por ser bit-a-bit idêntico a `app.icns` (confirmado por hash).
- `mysetup.exe` (instalador antigo, 58 MB) removido — os instaladores atuais passam
  a ser gerados pelo GitHub Actions e publicados como Release, não versionados no repo.

## Build automático (novo)

Adicionado `.github/workflows/build.yml`: ao criar uma tag `vX.Y`, compila o
instalador Windows (Inno Setup, numa runner `windows-latest`) e o `.dmg` macOS
(numa runner `macos-latest` — Apple não permite compilar `.app` fora de um Mac) e
publica os dois como Release no GitHub.

## v1.8 — Lista de Cues + deteção automática de slides

- Novo botão "📋 CUES" abre um painel para criar uma lista de cues (nº de slide +
  tempo + nome), reordenar, remover e gravar — persistida em
  `%APPDATA%\AVKtimer\cue_list.json` (macOS: `~/Library/Application Support/AVKtimer`),
  sobrevive a reinícios da app.
- Botão **NEXT** avança para a cue seguinte e arranca-a de imediato; também
  disponível via `/api/cue/next` (Companion/Stream Deck), além de
  `/api/cue/goto?indice=N`, `/api/cue/list` e `/api/cue/deteccao?ativo=1|0`.
- **Deteção automática**: com o toggle ligado, a app vigia o PowerPoint (Windows,
  via COM `SlideShowWindows.View.CurrentShowPosition`) ou o Keynote (macOS, via
  AppleScript) enquanto a apresentação está a decorrer; ao mudar para um slide com
  cue associada, carrega o tempo dessa cue e arranca a contagem sozinha.
- Fixado o número de versão no título da janela (`AVKtimer v1.8`) para nunca mais
  haver dúvida sobre qual build está a correr.
- `requirements.txt`: adicionado `pywin32` (só Windows) para a integração COM do
  PowerPoint.
- Corrigido o build macOS no CI: `build_mac.sh` estava sempre a nomear o `.dmg`
  como `v1.7` porque o workflow nunca lhe passava a versão da tag — o `.dmg` fica
  agora corretamente nomeado a partir da tag do release.

## v1.9 — Vigia de Slides (deteção em máquina separada)

- A deteção automática de slides (COM/PowerPoint e AppleScript/Keynote) só via o
  slide se corresse na mesma máquina que o AVKtimer. Como em régie normal o
  portátil de quem apresenta é outra máquina, foi criado um segundo executável
  leve, **AVKtimer Vigia de Slides** (`vigia_slides.py`), para correr nesse
  portátil: deteta o slide localmente e avisa a régie por HTTP.
- Nova rota `/api/cue/slide?numero=N` no AVKtimer principal, que recebe o aviso do
  Vigia e aplica a cue correspondente — só atua se a Deteção Automática estiver
  ligada no painel de Cues, o mesmo interruptor que já governava a deteção local.
- O Vigia é uma janela simples: um campo para o IP da régie (gravado entre
  sessões em `vigia_slides_config.json`, na mesma pasta de dados do AVKtimer) e
  um botão LIGAR/PARAR. Empacotado com instalador próprio para Windows e macOS
  (`packaging/windows/vigia.iss`, `packaging/macos/build_mac_vigia.sh`),
  compilado e publicado pelo mesmo workflow de CI.

## v1.9.1 — Assinatura ad-hoc no build macOS

- No Mac, foi reportado o aviso de segurança do Gatekeeper ao abrir os `.dmg`
  descarregados. Causa: os builds não são assinados por uma conta Apple Developer
  (paga), e o macOS marca automaticamente qualquer ficheiro descarregado da
  internet como "quarentena".
- Adicionado `codesign --force --deep --sign -` (assinatura ad-hoc, sem custo) a
  `build_mac.sh` e `build_mac_vigia.sh`, a seguir ao `xattr -cr`. Isto não elimina
  o aviso "de developer não identificado" — isso só se resolve com notarização
  Apple real, que exige conta paga — mas evita o modo de falha mais grave em Macs
  Apple Silicon ("app está danificada", sem botão de contornar nas Definições).
- Continua a ser preciso, na primeira vez, abrir com botão direito → Abrir (em
  vez de duplo clique) para confirmar a exceção do Gatekeeper.

## v1.9.2 — Corrigido o runner do build macOS (macos-13 foi retirado)

- A v1.9.1 nunca chegou a publicar-se: o job macos ficou preso em fila para
  sempre porque o runner `macos-13` (Intel) foi retirado pela GitHub em
  dezembro de 2025. Substituído por `macos-15-intel`, o runner Intel atual.
- Continua a ser um build Intel de propósito (corre nativamente em Mac Intel e
  via Rosetta 2 em Apple Silicon M1-M4) — ver comentário em `build.yml`. A
  GitHub já anunciou o fim do suporte Intel em macOS para depois do
  `macos-15` ser retirado (previsto outono de 2027); nessa altura é preciso
  mudar para build universal2 ou publicar dois `.dmg` separados.

## v2.0 — Rebrand para "Cue Timer" + paleta visual mais "tech"

- Nome visível trocado de "AVKtimer" para "Cue Timer" em todo o lado: título
  da janela, ecrã de palco, painel de Cues, bandeja do sistema, site
  things-on (nav, home, página própria) e nomes dos instaladores
  (`CueTimer_Setup_v2.0.exe`, `CueTimer_v2.0.dmg`,
  `CueTimer_VigiaSlides_v1.0.1_Setup.exe`). **Não alterado de propósito**: o
  repositório GitHub (continua `gitmike6453/AVKtimer`) e a pasta de dados do
  utilizador (`%APPDATA%\AVKtimer` / `~/Library/Application Support/AVKtimer`)
  — para não perder cue lists e configurações já gravadas por quem já usa a
  app. O `AppId` do instalador Windows também foi mantido igual, para o
  Windows tratar isto como uma atualização e não uma segunda instalação.
- Paleta de cores substituída: o fundo/paineis Dracula (roxo-acinzentado
  `#282a36` e família) passou a uma base azul-preto mais "tech"
  (`#0b0f1a`/`#141b28`/`#080b12`), e o cyan de destaque (`#00f0ff`) alinhado
  ao cyan de marca do site (`#3fd6ea`), a mesma referência usada no ícone do
  Cue Timer em things-on.mike-app.com.
- Os botões de ação (INICIAR/PAUSAR/STOP/etc, toggles ECRÃ/SOM/PISCAR,
  MODO RELÓGIO) tinham preenchimentos em cores primárias muito saturadas
  (verde/vermelho/âmbar/cyan "vivos"), o que lia como infantil/"caixa de
  lápis de cor" -- aprofundados para tons mais escuros e dessaturados
  (`#0d9488` verde-petróleo, `#b91c1c` vermelho profundo, `#b45309` âmbar
  profundo, `#0e7490`/`#0891b2` cyan profundo), mantendo o texto/legendas em
  cores mais claras e legíveis para não perder contraste.
- `vigia_slides.py` recebeu a mesma paleta e o mesmo rebrand de nome, para
  as duas apps continuarem visualmente consistentes.

## Por verificar/decidir (não alterado)

- `/api/som/set_webhooks` só permite definir remotamente o webhook H1 (H2/H3 só
  pelo painel local) — comportamento original mantido, documentado no README.
- `templates/index.html` (visor web) não aplica o campo `tamanho_fonte` devolvido
  por `/status` (só o ecrã de palco nativo o faz) — pode ser intencional (o web usa
  escala responsiva em `vw`); não alterado sem confirmação.
- Para eliminar por completo o aviso "developer não identificado" no Mac (não só o
  modo "danificada") é preciso notarização Apple real, o que exige uma conta Apple
  Developer paga (99$/ano) associada a este projeto — por decidir se vale a pena.
