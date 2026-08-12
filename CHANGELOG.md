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

## Por verificar/decidir (não alterado)

- `/api/som/set_webhooks` só permite definir remotamente o webhook H1 (H2/H3 só
  pelo painel local) — comportamento original mantido, documentado no README.
- `templates/index.html` (visor web) não aplica o campo `tamanho_fonte` devolvido
  por `/status` (só o ecrã de palco nativo o faz) — pode ser intencional (o web usa
  escala responsiva em `vw`); não alterado sem confirmação.
