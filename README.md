# AVKtimer

Cronómetro/relógio de estúdio para régie, com painel de operador (Tkinter), ecrã de
palco secundário, visor web para OBS/browser, e uma API HTTP completa para controlo
remoto a partir do [Bitfocus Companion](https://bitfocus.io/companion) (Stream Deck).

Corre de forma nativa em **Windows** e **macOS** a partir do mesmo código
(`avktimer.py`), com deteção automática do sistema operativo em tempo de execução.

## Funcionalidades

- Cronómetro com contagem decrescente, modo negativo (continua após zero) e modo relógio.
- Ecrã de palco secundário (janela nativa, suporta segundo monitor).
- Visor web (`http://<ip>:4545`) para usar como fonte de browser no OBS/vMix.
- Mensagens rápidas pré-definidas (10 slots) e mensagem livre.
- 3 alarmes sonoros independentes com gatilho por segundo restante.
- 3 automações HTTP/TCP externas (inclui suporte a comandos brutos TCP do Companion, porta 16759).
- API HTTP completa para o Companion (ver abaixo) e módulo dedicado em `companion-plugins/`.

## Correr a partir do código-fonte

```bash
pip install -r requirements.txt
python avktimer.py
```

## Construir os instaladores

### Windows (local)

```bash
pip install -r requirements.txt
pyinstaller packaging/windows/AVKtimer.spec
# Requer o Inno Setup instalado (https://jrsoftware.org/isinfo.php)
ISCC packaging\windows\avk.iss
```
O instalador final fica em `Output/`.

### macOS (local, tem de correr num Mac)

```bash
bash packaging/macos/build_mac.sh
```
Produz `dist/AVKtimer.app` e `dist/AVKtimer_v1.7.dmg`.

### Automático (GitHub Actions)

Ao publicar uma tag `vX.Y` (ex: `git tag v1.7 && git push origin v1.7`), o workflow
`.github/workflows/build.yml` compila automaticamente o instalador Windows (numa
runner `windows-latest`) e o `.dmg` macOS (numa runner `macos-latest`, já que a Apple
não permite compilar `.app` fora de um Mac) e publica ambos numa Release do GitHub.
Também pode ser corrido manualmente pela aba "Actions" (`workflow_dispatch`).

## API HTTP (para o Companion / automação externa)

Servidor Flask na porta `4545`. Todos os endpoints são `GET`.

| Rota | Descrição |
|---|---|
| `/status` | Estado atual em JSON (tempo, cor/estado, fonte, mensagem, modo) |
| `/api/iniciar` | Inicia a contagem |
| `/api/pausar` | Pausa a contagem |
| `/api/stop` | Para e zera |
| `/api/reset` | Repõe o último tempo configurado (sem iniciar) |
| `/api/reiniciar` | Repõe o último tempo configurado e inicia |
| `/api/atualizar` | Aplica o tempo escrito nas caixas H/M/S |
| `/api/modo_web` | Alterna entre modo Timer e modo Relógio |
| `/api/toggle_piscar` | Liga/desliga o piscar pós-zero |
| `/api/ecran_on` | Liga o ecrã de palco |
| `/api/ecran_off` | Desliga o ecrã de palco |
| `/api/tempo/mais_hora` / `menos_hora` | +/- 1 hora (na caixa, antes de Atualizar) |
| `/api/tempo/mais_min` / `menos_min` | +/- 1 minuto |
| `/api/tempo/mais_seg` / `menos_seg` | +/- 5 segundos |
| `/api/tempo/set?horas=&minutos=&segundos=` | Define o tempo exato (só quando parado) |
| `/api/fonte/tamanho?valor=` ou `?ajuste=plus\|minus` | Tamanho da fonte no palco |
| `/api/msg?texto=...` | Envia mensagem livre para o palco/web |
| `/api/limpar_msg` | Limpa a mensagem |
| `/api/som/set_triggers?t1=&t2=&t3=` | Define os segundos-gatilho dos 3 alarmes sonoros |
| `/api/som/set_webhooks?h1_seg=&h1_url=` | Define o gatilho/URL do webhook H1 (H2/H3 só via painel local) |

## Módulo Companion dedicado

Em alternativa a usar o módulo genérico "HTTP" do Companion com as rotas acima,
`companion-plugins/` contém um módulo dedicado com todas as ações já listadas por
nome, mais variáveis (`tempo`, `estado`, `mensagem`, `modo_web`) para usar no texto
dos botões do Stream Deck. Ver `companion-plugins/README` do próprio Companion para
como instalar módulos de desenvolvimento local.

## Dados do utilizador

Sons customizados carregados pelo botão "BUSCAR" são gravados em:
- Windows: `%APPDATA%\AVKtimer\`
- macOS: `~/Library/Application Support/AVKtimer/`

(Antes gravavam na pasta de arranque do programa, o que falhava silenciosamente
quando instalado em `Program Files`.)

## Notas de segurança

Este repositório **não** inclui o binário `cloudflared` nem tokens de túnel que
existiam na pasta de desenvolvimento original — se usavas um túnel Cloudflare para
expor o servidor à internet, gera um novo token e guarda-o fora do controlo de
versões (ex: variável de ambiente).
