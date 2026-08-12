import os
import sys
import socket
import threading
import time
import datetime
import json
import subprocess
import warnings
from tkinter import Tk, Label, Entry, Button, StringVar, messagebox, Frame, Canvas, Toplevel, Scale, Listbox
from tkinter.ttk import Combobox
from tkinter import filedialog
from flask import Flask, render_template, jsonify, request

# 💥 PRIMEIRO: Define a variável global do sistema para o Python a memorizar logo no boot
SISTEMA_MAC = (sys.platform == "darwin")

# 💥 SEGUNDO: Se for Mac, injeta o motor de botões coloridos corrigido
if SISTEMA_MAC:
    try:
        from tkmacosx import Button
    except ImportError:
        pass


# Silencia os avisos inofensivos do Pillow sobre o tamanho do arquivo app.ico
warnings.filterwarnings("ignore", category=UserWarning, module="PIL")

app = Flask(__name__)

# Configuração de caminhos estáveis para o executável (OneFile) no Mac e Windows
if getattr(sys, 'frozen', False):
    caminho_base = sys._MEIPASS
else:
    caminho_base = os.path.dirname(os.path.abspath(__file__))

app.template_folder = os.path.join(caminho_base, 'templates')
app.static_folder = os.path.join(caminho_base, 'static')

comando_atualizar_remoto_pendente = False


def obter_pasta_dados_utilizador():
    """Devolve uma pasta gravável para dados do utilizador (sons customizados),
    independente de onde o executável foi instalado (ex: Program Files é read-only)."""
    if SISTEMA_MAC:
        pasta = os.path.join(os.path.expanduser("~/Library/Application Support"), "AVKtimer")
    else:
        pasta = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AVKtimer")
    os.makedirs(pasta, exist_ok=True)
    return pasta


PASTA_DADOS_UTILIZADOR = obter_pasta_dados_utilizador()
CAMINHO_CUES_JSON = os.path.join(PASTA_DADOS_UTILIZADOR, "cue_list.json")


def carregar_lista_cues():
    """Recupera a lista de cues gravada da última sessão (se existir)."""
    global lista_cues
    try:
        if os.path.exists(CAMINHO_CUES_JSON):
            with open(CAMINHO_CUES_JSON, "r", encoding="utf-8") as ficheiro:
                lista_cues = json.load(ficheiro)
    except Exception as e:
        print(f"[Cue List] Erro ao carregar lista gravada: {e}")


def gravar_lista_cues():
    """Persiste a lista de cues em disco para sobreviver ao fecho da aplicação."""
    try:
        with open(CAMINHO_CUES_JSON, "w", encoding="utf-8") as ficheiro:
            json.dump(lista_cues, ficheiro, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Cue List] Erro ao gravar lista: {e}")

# =========================================================================
# INICIALIZAÇÃO DA INTERFACE GRÁFICA (CÁLCULO DE RESOLUÇÃO E FIXAÇÃO DE ÍCONE)
# =========================================================================
if not SISTEMA_MAC:
    import ctypes
    # 💥 TRANCA DE ENGENHARIA: Fixa o ícone corporativo na Barra de Tarefas do Windows!
    try:
        meu_app_id = 'avkstudio.avktimer.studio.v13'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(meu_app_id)
    except Exception:
        pass

root = Tk()
root.title("Cue Timer v2.1")
root.withdraw()

LARGURA_ECRA = root.winfo_screenwidth()
ALTURA_ECRA = root.winfo_screenheight()

# Define a janela de operação para 80% do tamanho do monitor detetado
LARGURA_JANELA = int(LARGURA_ECRA * 0.80)
ALTURA_JANELA = int(ALTURA_ECRA * 0.80)

pos_x = int((LARGURA_ECRA / 2) - (LARGURA_JANELA / 2))
pos_y = int((ALTURA_ECRA / 2) - (ALTURA_JANELA / 2))

# --- ENGINE MATEMÁTICO DE ESCALA ADAPTATIVA ULTRA-EXPANDIDA ---
fator_escala = ALTURA_ECRA / 1080.0
tempo_inicial_memoria = 3600  # Guarda o último preset ou tempo de arranque


def calcular_fonte(tamanho_base):
    """Calcula dinamicamente a fonte e aplica +50% de ganho para máxima legibilidade."""
    novo_tamanho = int(tamanho_base * fator_escala * 1.50)
    return max(12, novo_tamanho)

def calcular_pading(pading_base):
    """Aumenta o espaçamento interno para afastar as caixas do texto grande."""
    novo_pading = int(pading_base * fator_escala * 1.30)
    return max(4, novo_pading)

# =========================================================================
# VARIÁVEIS GLOBAIS DE CONTROLO DO CRONÓMETRO
# =========================================================================
tempo_restante = 3600  # Começa por padrão em 01:00:00 (1 hora)
executando = False
fonte_atual = "Arial"
modo_negativo = False   # Permite contagem contínua pós-zero
modo_visualizacao = "timer"
permitir_piscar_pos_zero = True  # Flag de controlo do botão Blink
veio_de_stop_manual = False      # Evita o piscar em repouso após o STOP

# Configurações dinâmicas de alertas visuais (Minutos)
minutos_alerta = 3
minutos_critico = 1

# Presets Rápidos em segundos puros [30s, 1m, 2m, 3m, 5m, 10m, 15m, 20m, 30m, 60m]
valores_presets = [30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600]
botoes_presets_referencias = []
# =========================================================================
# INITIALIZATION CORE: VARIÁVEIS DE TEXTO COM slots ALOCADOS (10 POSIÇÕES)
# =========================================================================
global textos_presets_msg, botoes_msg_referencias, mensagem_global, estado_mensagem_anterior

# Aloca estritamente as tuas 4 mensagens core + 6 slots livres para perfazer os 10 botões da grelha
textos_presets_msg = [
    "INTERVALO",
    "ENTRADA LIVRE",
    "ATENÇÃO",
    "FIM DE SESSÃO",
    "PRESET 5",
    "PRESET 6",
    "PRESET 7",
    "PRESET 8",
    "PRESET 9",
    "PRESET 10"
]

botoes_msg_referencias = []
mensagem_global = ""
estado_mensagem_anterior = ""

# Referências das Janelas e Ecrãs
janela_principal = None
janela_secundaria = None
lbl_tempo_secundario = None
lbl_msg_secundaria = None
frame_conteudo_secundario = None
lbl_status_tk = None
janela_fullscreen = False

# =========================================================================
# VARIÁVEIS GLOBAIS DE ÁUDIO & AUTOMAÇÃO INDEPENDENTE
# =========================================================================
som_ativado = True          # Mute/Unmute geral do painel
volume_global = 70          # Escala de volume de 0 a 100%

# Configuração elástica de seleção de som para cada um dos 3 alarmes
som_selecionado_1 = "Bip"
som_selecionado_2 = "Bip"
som_selecionado_3 = "Bip"

gatilho_som_1 = -1
gatilho_som_2 = -1
gatilho_som_3 = -1

som_tocado_trig_1 = False
som_tocado_trig_2 = False
som_tocado_trig_3 = False

# Configuração de até 3 triggers HTTP/TCP para a Régie
trig_http_seg_1 = -1
trig_http_seg_2 = -1
trig_http_seg_3 = -1

trig_http_url_1 = ""
trig_http_url_2 = ""
trig_http_url_3 = ""

trig_http_met_1 = "GET"
trig_http_met_2 = "GET"
trig_http_met_3 = "GET"

enviado_http_1 = False
enviado_http_2 = False
enviado_http_3 = False

# =========================================================================
# LISTA DE CUES: cada cue é {"slide": int, "tempo": segundos, "nome": str}
# =========================================================================
lista_cues = []
indice_cue_atual = -1
deteccao_automatica_ativa = False
ultimo_slide_detectado = None
janela_cues = None
# =========================================================================
# DETEÇÃO DE IP E CONFIGURAÇÃO INICIAL DO FLASK
# =========================================================================
def obter_ip_local():
    """Faz um varrimento completo a todas as placas de rede do PC para achar o IP real."""
    try:
        import psutil
        ips_validos = []
        interfaces = psutil.net_if_addrs()
        for nome_placa, enderecos in interfaces.items():
            for endereco in enderecos:
                if endereco.family == socket.AF_INET:
                    ip = endereco.address
                    if not ip.startswith("127.") and not ip.startswith("169.254."):
                        if ip not in ips_validos:
                            ips_validos.append(ip)
        if ips_validos:
            return " | ".join(ips_validos)
        return "127.0.0.1"
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_ativo = s.getsockname()[0]
            s.close()
            return ip_ativo
        except Exception:
            return "127.0.0.1"


def iniciar_servidor_flask():
    """Valida o arranque da rede e atualiza de forma segura a barra de logs no topo da UI."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    time.sleep(1.5)

    try:
        ip_real = obter_ip_local()
        mensagem_sucesso = f"Servidor disponível em: http://{ip_real}:4545"

        if 'lbl_ips_rede' in globals() and lbl_ips_rede is not None:
            root.after(0, lambda: lbl_ips_rede.config(text=mensagem_sucesso, fg="#22c55e"))

        app.run(host='0.0.0.0', port=4545, debug=False, use_reloader=False, threaded=True)

    except Exception:
        mensagem_erro = "Erro: Porta de rede bloqueada ou ocupada!"
        if 'lbl_ips_rede' in globals() and lbl_ips_rede is not None:
            root.after(0, lambda: lbl_ips_rede.config(text=mensagem_erro, fg="#ef4444"))


@app.route('/')
def home():
    user_agent = request.headers.get('User-Agent', '')
    if "Companion" in user_agent or request.args.get('companion') == '1':
        return jsonify({"status": "online", "dispositivo": "Cue Timer Server"})

    try:
        caminho_direto_html = os.path.join(caminho_base, 'templates', 'index.html')
        with open(caminho_direto_html, 'r', encoding='utf-8') as ficheiro:
            return ficheiro.read()
    except Exception:
        return render_template('index.html')
# =========================================================================
# ROTAS DA API WEB (FLASK) - COMANDOS CORE & AJUSTES
# =========================================================================
@app.route('/status')
def status():
    global tempo_restante, fonte_atual, mensagem_global, minutos_alerta, minutos_critico, modo_visualizacao, veio_de_stop_manual, tamanho_fonte_timer_atual

    tempo_formatado = formatar_tempo_completo(tempo_restante)

    estado_cor = "normal"
    if veio_de_stop_manual:
        estado_cor = "normal"
    elif tempo_restante <= 0:
        estado_cor = "fim"
    elif tempo_restante <= (minutos_critico * 60):
        estado_cor = "critico"
    elif tempo_restante <= (minutos_alerta * 60):
        estado_cor = "alerta"

    return jsonify({
        "tempo": tempo_formatado,
        "estado": estado_cor,
        "fonte": fonte_atual,
        "tamanho_fonte": tamanho_fonte_timer_atual if 'tamanho_fonte_timer_atual' in globals() else 150,
        "mensagem": mensagem_global,
        "modo_web": modo_visualizacao
    })

# =========================================================================
# NOVAS ROTAS DE API PARA COMPANION (OVERRIDE, BLINK E TAMANHO DA FONTE)
# =========================================================================

@app.route('/api/atualizar')
def api_atualizar_override():
    """Gatilha o comando ATUALIZAR remotamente de forma blindada contra linhas de cache compiladas."""
    global comando_atualizar_remoto_pendente
    comando_atualizar_remoto_pendente = True
    return jsonify({"status": "sucesso", "acao": "override_agendado"})




@app.route('/api/toggle_piscar')
def api_toggle_piscar():
    """Ativa ou desativa a permissão do Blink pós-zero via Companion."""
    root.after(0, toggle_permissao_piscar)
    return jsonify({"status": "sucesso"})


@app.route('/api/fonte/tamanho')
def api_definir_tamanho_fonte():
    """Altera o tamanho do texto do relógio no palco. Ex: /api/fonte/tamanho?valor=180 ou ?ajuste=plus/?ajuste=minus"""
    global tamanho_fonte_timer_atual, lbl_tempo_secundario, fonte_atual
    try:
        if not 'tamanho_fonte_timer_atual' in globals():
            tamanho_fonte_timer_atual = 150

        valor = request.args.get('valor')
        ajuste = request.args.get('ajuste')

        if valor:
            tamanho_fonte_timer_atual = max(30, min(400, int(valor)))
        elif ajuste == "plus":
            tamanho_fonte_timer_atual = min(400, tamanho_fonte_timer_atual + 10)
        elif ajuste == "minus":
            tamanho_fonte_timer_atual = max(30, tamanho_fonte_timer_atual - 10)

        # Atualiza a interface gráfica do palco instantaneamente se ela estiver aberta
        if 'lbl_tempo_secundario' in globals() and lbl_tempo_secundario and lbl_tempo_secundario.winfo_exists():
            root.after(0, lambda: lbl_tempo_secundario.config(font=(fonte_atual, calcular_fonte(tamanho_fonte_timer_atual), "bold")))

        return jsonify({"status": "sucesso", "novo_tamanho": tamanho_fonte_timer_atual})
    except Exception as e:
        return jsonify({"status": "erro", "motivo": str(e)})


@app.route('/api/iniciar')
def api_iniciar():
    root.after(0, iniciar_timer)
    return jsonify({"status": "sucesso"})


@app.route('/api/pausar')
def api_pausar():
    root.after(0, pausar_timer)
    return jsonify({"status": "sucesso"})


@app.route('/api/stop')
def api_stop():
    root.after(0, parar_timer)
    return jsonify({"status": "sucesso"})

@app.route('/api/reset')
def api_reset_timer_direto():
    """Gatilha o Reset Macro via HTTP (PAUSE -> REPOR CAIXAS -> LIBERTAR TRINCOS)."""
    try:
        if 'root' in globals() and root and 'reset_timer_local' in globals():
            root.after(0, reset_timer_local)
            return jsonify({"status": "sucesso", "acao": "reset_to_time_executado"})
        return jsonify({"status": "erro", "motivo": "Janela nao inicializada"})
    except Exception as e:
        return jsonify({"status": "erro", "motivo": str(e)})


@app.route('/api/reiniciar')
def api_comando_reiniciar_exclusivo_companion():
    """Gatilha o Reiniciar Corrido via HTTP (PAUSE -> REPOR -> DISPARAR PLAY ASSÍNCRONO)."""
    try:
        if 'root' in globals() and root and 'reiniciar_timer' in globals():
            # Despacha para a thread gráfica ativar a flag executando = True diretamente
            root.after(0, reiniciar_timer)
            return jsonify({"status": "sucesso", "acao": "reiniciar_e_correndo_executado"})
        return jsonify({"status": "erro", "motivo": "Root ou funcao nao inicializada"})
    except Exception as e:
        return jsonify({"status": "erro", "motivo": str(e)})


@app.route('/api/modo_web')
def api_modo_web():
    root.after(0, alternar_modo_visualizacao)
    return jsonify({"status": "sucesso"})


@app.route('/api/limpar_msg')
def api_limpar_msg():
    root.after(0, limpar_mensagem_ecra)
    return jsonify({"status": "sucesso"})


@app.route('/api/ecran_on')
def api_ecran_on():
    root.after(0, generar_janela_nativa_directx)
    return jsonify({"status": "sucesso", "acao": "ecran_ligado_no_palco"})


@app.route('/api/ecran_off')
def api_ecran_off():
    root.after(0, fechar_ecran_nativo_botao)
    return jsonify({"status": "sucesso", "acao": "ecran_desligado_no_palco"})


@app.route('/api/tempo/mais_hora')
def api_mais_hora():
    root.after(0, lambda: alterar_horas(1))
    return jsonify({"status": "sucesso"})


@app.route('/api/tempo/menos_hora')
def api_menos_hora():
    root.after(0, lambda: alterar_horas(-1))
    return jsonify({"status": "sucesso"})


@app.route('/api/tempo/mais_min')
def api_mais_min():
    root.after(0, lambda: alterar_minutos(1))
    return jsonify({"status": "sucesso"})


@app.route('/api/tempo/menos_min')
def api_menos_min():
    root.after(0, lambda: alterar_minutos(-1))
    return jsonify({"status": "sucesso"})


@app.route('/api/tempo/mais_seg')
def api_mais_seg():
    root.after(0, lambda: alterar_segundos(5))
    return jsonify({"status": "sucesso"})


@app.route('/api/tempo/menos_seg')
def api_menos_seg():
    root.after(0, lambda: alterar_segundos(-5))
    return jsonify({"status": "sucesso"})


@app.route('/api/msg')
def api_msg():
    global mensagem_global
    texto = request.args.get('texto', '')
    if texto:
        mensagem_global = texto
        try:
            root.after(0, lambda: atualizar_campo_mensagem_ui(texto))
        except Exception:
            pass
        return jsonify({"status": "sucesso"})
    return jsonify({"status": "erro"})


@app.route('/api/tempo/set')
def api_set_tempo():
    global tempo_restante, executando
    try:
        hrs = int(request.args.get('horas', 0))
        mins = int(request.args.get('minutos', 0))
        segs = int(request.args.get('segundos', 0))
        segundos_totais = (hrs * 3600) + (mins * 60) + segs
        if not executando:
            root.after(0, lambda: entry_horas.delete(0, 'end'))
            root.after(0, lambda: entry_horas.insert(0, f"{hrs:02d}"))
            root.after(0, lambda: entry_minutos.delete(0, 'end'))
            root.after(0, lambda: entry_minutos.insert(0, f"{mins:02d}"))
            root.after(0, lambda: entry_segundos.delete(0, 'end'))
            root.after(0, lambda: entry_segundos.insert(0, f"{segs:02d}"))
            root.after(0, lambda: atualizar_tempo_por_inputs())
            return jsonify({"status": "sucesso", "segundos_totais": segundos_totais})
        else:
            return jsonify({"status": "erro", "motivo": "Timer em execucao. Pausa primeiro."})
    except ValueError:
        return jsonify({"status": "erro", "motivo": "Parametros invalidos."})


@app.route('/api/som/set_triggers')
def api_definir_multi_triggers():
    global gatilho_som_1, gatilho_som_2, gatilho_som_3
    try:
        t1 = request.args.get('t1')
        t2 = request.args.get('t2')
        t3 = request.args.get('t3')
        if t1 is not None:
            gatilho_som_1 = int(t1) if t1.strip() else -1
            root.after(0, lambda: entry_trig_som1.delete(0, 'end') or entry_trig_som1.insert(0, str(t1)))
        if t2 is not None:
            gatilho_som_2 = int(t2) if t2.strip() else -1
            root.after(0, lambda: entry_trig_som2.delete(0, 'end') or entry_trig_som2.insert(0, str(t2)))
        if t3 is not None:
            gatilho_som_3 = int(t3) if t3.strip() else -1
            root.after(0, lambda: entry_trig_som3.delete(0, 'end') or entry_trig_som3.insert(0, str(t3)))
        return jsonify({"status": "sucesso"})
    except ValueError:
        return jsonify({"status": "erro"})


@app.route('/api/som/set_webhooks')
def api_definir_multi_webhooks():
    global trig_http_seg_1, trig_http_url_1
    try:
        h1_s = request.args.get('h1_seg')
        h1_u = request.args.get('h1_url')
        if h1_s is not None:
            trig_http_seg_1 = int(h1_s) if h1_s.strip() else -1
            root.after(0, lambda: entry_http_seg1.delete(0, 'end') or entry_http_seg1.insert(0, str(h1_s)))
        if h1_u is not None:
            trig_http_url_1 = h1_u
            root.after(0, lambda: entry_http_url1.delete(0, 'end') or entry_http_url1.insert(0, h1_u))
        atualizar_gatilhos_http_via_painel()
        return jsonify({"status": "sucesso"})
    except ValueError:
        return jsonify({"status": "erro"})


# =========================================================================
# ROTAS DE API PARA A LISTA DE CUES (NEXT MANUAL + COMPANION/STREAM DECK)
# =========================================================================
@app.route('/api/cue/next')
def api_cue_next():
    """Avança para a cue seguinte da lista — mesma ação do botão NEXT no painel."""
    avancar_cue_next()
    return jsonify({"status": "sucesso"})


@app.route('/api/cue/goto')
def api_cue_goto():
    """Salta diretamente para a cue de índice indicado (0-based). Ex: /api/cue/goto?indice=2"""
    try:
        idx = int(request.args.get('indice', -1))
        if idx < 0 or idx >= len(lista_cues):
            return jsonify({"status": "erro", "motivo": "indice fora da lista"})
        root.after(0, lambda: aplicar_cue(idx))
        return jsonify({"status": "sucesso"})
    except Exception as e:
        return jsonify({"status": "erro", "motivo": str(e)})


@app.route('/api/cue/list')
def api_cue_list():
    """Devolve a lista de cues atual e qual está ativa, para consumo externo (Companion)."""
    return jsonify({"cues": lista_cues, "indice_atual": indice_cue_atual})


@app.route('/api/cue/slide')
def api_cue_slide():
    """Recebe o número de slide detetado por um Vigia de Slides externo (noutra máquina, ex: o
    portátil de quem apresenta) e aplica a cue correspondente. Só atua se a Deteção Automática
    estiver ligada no painel de Cues -- assim o mesmo interruptor governa a deteção local e a remota."""
    global ultimo_slide_detectado
    if not deteccao_automatica_ativa:
        return jsonify({"status": "ignorado", "motivo": "deteccao automatica desligada"})
    try:
        numero = int(request.args.get('numero', -1))
        if numero < 0:
            return jsonify({"status": "erro", "motivo": "numero invalido"})
        ultimo_slide_detectado = numero
        encontrou = ir_para_cue_por_slide(numero)
        if 'lbl_deteccao_status' in globals() and lbl_deteccao_status:
            texto = f"Slide atual (remoto): {numero}" + ("" if encontrou else " (sem cue associada)")
            root.after(0, lambda t=texto: lbl_deteccao_status.config(text=t, fg="#34d399"))
        return jsonify({"status": "sucesso", "slide": numero, "cue_encontrada": encontrou})
    except Exception as e:
        return jsonify({"status": "erro", "motivo": str(e)})


@app.route('/api/cue/deteccao')
def api_cue_deteccao():
    """Liga/desliga a deteção automática de slides via rede. Ex: /api/cue/deteccao?ativo=1"""
    global deteccao_automatica_ativa
    valor = request.args.get('ativo')
    if valor is not None:
        deteccao_automatica_ativa = valor.strip().lower() in ("1", "true", "on", "sim")
        root.after(0, atualizar_botao_deteccao_ui)
    return jsonify({"status": "sucesso", "ativo": deteccao_automatica_ativa})


# =========================================================================
# FUNÇÕES DE SUPRESSÃO DE HORAS E AUTOMAÇÃO ASSÍNCRONA HÍBRIDA
# =========================================================================
def formatar_tempo_completo(segundos_totais):
    """Converte segundos para formato MM:SS ou HH:MM:SS, ocultando as horas se forem zero."""
    sinal = "-" if segundos_totais < 0 else ""
    t_abs = abs(segundos_totais)
    horas = t_abs // 3600
    minutos = (t_abs % 3600) // 60
    segundos = t_abs % 60
    if horas == 0:
        return f"{sinal}{minutos:02d}:{segundos:02d}"
    else:
        # CORREÇÃO: Reinjetado o ":" entre as horas e os minutos
        return f"{sinal}{horas:02d}:{minutos:02d}:{segundos:02d}"



def executar_pedido_externo_assincrono(url, metodo, headers, body):
    """Executa pedidos Web (HTTP) ou comandos brutos de régie via Socket TCP (porta 16759 do Companion)."""
    try:
        linha_comando = url.strip()

        # --- 💻 CANAL EXCLUSIVO TCP BRUTO (Companion porta 16759) ---
        if "16759" in linha_comando:
            comando_limpo = linha_comando.replace("http://", "").replace("https://", "")
            partes = comando_limpo.split("/", 1)

            host_porto = partes[0].split(":")
            host = host_porto[0]
            porto = int(host_porto[1])
            comando_bruto = partes[1] if len(partes) > 1 else ""

            if comando_bruto:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((host, porto))

                # CORREÇÃO DA RÉGIE: Injeta a quebra de linha \r\n exigida pelo protocolo do Companion
                pacote_final = f"{comando_bruto}\r\n"
                s.sendall(pacote_final.encode('utf-8'))
                s.close()
                print(f"[Gatilho TCP Companion Executado] String enviada: {comando_bruto}")
                return

        # --- 🌐 CANAL FLUXO PADRÃO WEB (HTTP GET/POST) ---
        metodo = metodo.upper()
        if not linha_comando.startswith("http://") and not linha_comando.startswith("https://"):
            linha_comando = "http://" + linha_comando

        import requests
        if metodo == "GET":
            requests.get(linha_comando, headers=headers, timeout=3)
        elif metodo == "POST":
            requests.post(linha_comando, json=body if isinstance(body, dict) else None,
                          data=body if not isinstance(body, dict) else None, headers=headers, timeout=3)
        print(f"[Gatilho HTTP Web] Pedido enviado para {linha_comando}")
    except Exception as e:
        print(f"[Gatilho API] Erro ao enviar automacao externa: {e}")


# Inicializa a flag de proteção de thread no escopo global do ficheiro
if 'thread_relogio_ativa' not in globals():
    thread_relogio_ativa = False


def contagem_decrescente():
    """Gere o relógio principal da Régie de forma assíncrona com proteção estrita de Thread Única."""
    global tempo_restante, executando, modo_negativo, lbl_status_tk, lbl_preview_regie_tk
    global gatilho_som_1, gatilho_som_2, gatilho_som_3
    global som_tocado_trig_1, som_tocado_trig_2, som_tocado_trig_3
    global trig_http_seg_1, trig_http_seg_2, trig_http_seg_3
    global enviado_http_1, enviado_http_2, enviado_http_3
    global comando_atualizar_remoto_pendente
    global thread_relogio_ativa

    # ─── 💥 TRINCO DE ENGENHARIA BROADCAST (Mata o Conflito de Threads Duplicadas) ───
    if thread_relogio_ativa:
        print("[Motor Relógio] Aviso: Tentativa de disparo duplicado bloqueada com sucesso.")
        return

    thread_relogio_ativa = True
    print("[Motor Relógio] Thread assíncrona mestre inicializada com segurança total.")

    if 'comando_atualizar_remoto_pendente' not in globals():
        comando_atualizar_remoto_pendente = False

    while True:
        try:
            if comando_atualizar_remoto_pendente:
                comando_atualizar_remoto_pendente = False
                if 'root' in globals() and root is not None and 'executar_override_tempo' in globals():
                    root.after(0, executar_override_tempo)

            if executando:
                # 1. Desconto firme de 1 segundo real em memória
                tempo_restante -= 1

                # 2. Injeção isolada e assíncrona nas variáveis do ecrã
                def atualizar_todos_os_visores_feedback_ui():
                    try:
                        txt_formatado = formatar_tempo_completo(tempo_restante)

                        # Monitor de Palco e Preview Local da Régie
                        if 'lbl_status_tk' in globals() and lbl_status_tk:
                            lbl_status_tk.set(f"Tempo: {txt_formatado}")
                        if 'lbl_preview_regie_tk' in globals() and lbl_preview_regie_tk:
                            lbl_preview_regie_tk.set(f"Tempo: {txt_formatado}")

                        # --- VISORES DE ALARMES DE ÁUDIO (T1, T2, T3) ---
                        if 'lbl_som_feedback1' in globals() and lbl_som_feedback1:
                            if gatilho_som_1 != -1 and tempo_restante >= gatilho_som_1:
                                lbl_som_feedback1.config(text=f"Falta {tempo_restante - gatilho_som_1}s", fg="#34d399")
                            else:
                                lbl_som_feedback1.config(text="---", fg="#7d97a3")

                        if 'lbl_som_feedback2' in globals() and lbl_som_feedback2:
                            if gatilho_som_2 != -1 and tempo_restante >= gatilho_som_2:
                                lbl_som_feedback2.config(text=f"Falta {tempo_restante - gatilho_som_2}s", fg="#34d399")
                            else:
                                lbl_som_feedback2.config(text="---", fg="#7d97a3")

                        if 'lbl_som_feedback3' in globals() and lbl_som_feedback3:
                            if gatilho_som_3 != -1 and tempo_restante >= gatilho_som_3:
                                lbl_som_feedback3.config(text=f"Falta {tempo_restante - gatilho_som_3}s", fg="#34d399")
                            else:
                                lbl_som_feedback3.config(text="---", fg="#7d97a3")

                        # --- VISORES DE REDE HTTP (H1, H2, H3) ---
                        if 'lbl_http_feedback1' in globals() and lbl_http_feedback1:
                            if trig_http_seg_1 != -1 and tempo_restante >= trig_http_seg_1:
                                lbl_http_feedback1.config(text=f"Falta {tempo_restante - trig_http_seg_1}s",
                                                          fg="#34d399")
                            else:
                                lbl_http_feedback1.config(text="---", fg="#7d97a3")

                        if 'lbl_http_feedback2' in globals() and lbl_http_feedback2:
                            if trig_http_seg_2 != -1 and tempo_restante >= trig_http_seg_2:
                                lbl_http_feedback2.config(text=f"Falta {tempo_restante - trig_http_seg_2}s",
                                                          fg="#34d399")
                            else:
                                lbl_http_feedback2.config(text="---", fg="#7d97a3")

                        if 'lbl_http_feedback3' in globals() and lbl_http_feedback3:
                            if trig_http_seg_3 != -1 and tempo_restante >= trig_http_seg_3:
                                lbl_http_feedback3.config(text=f"Falta {tempo_restante - trig_http_seg_3}s",
                                                          fg="#34d399")
                            else:
                                lbl_http_feedback3.config(text="---", fg="#7d97a3")
                    except Exception:
                        pass

                if 'root' in globals() and root:
                    root.after(0, atualizar_todos_os_visores_feedback_ui)

                    # 💥 VERIFICA SE O BLOCO 3 DENTRO DO TEU LOOP SE ENCONTRA EXATAMENTE ASSIM:

                    # --- 🔊 3. DISPARO DOS ALARMES DE ÁUDIO NO SEGUNDO EXATO ---
                    if gatilho_som_1 != -1 and tempo_restante == gatilho_som_1 and not som_tocado_trig_1:
                        som_tocado_trig_1 = True
                        print(f"🔊 [GATILHO ÁUDIO] Alarme T1 disparado na marca dos {gatilho_som_1}s!")
                        threading.Thread(target=tocar_som_background, args=(1,), daemon=True).start()

                    if gatilho_som_2 != -1 and tempo_restante == gatilho_som_2 and not som_tocado_trig_2:
                        som_tocado_trig_2 = True
                        print(f"🔊 [GATILHO ÁUDIO] Alarme T2 disparado na marca dos {gatilho_som_2}s!")
                        threading.Thread(target=tocar_som_background, args=(2,), daemon=True).start()

                    if gatilho_som_3 != -1 and tempo_restante == gatilho_som_3 and not som_tocado_trig_3:
                        som_tocado_trig_3 = True
                        print(f"🔊 [GATILHO ÁUDIO] Alarme T3 disparado na marca dos {gatilho_som_3}s!")
                        threading.Thread(target=tocar_som_background, args=(3,), daemon=True).start()

                # --- 🌐 4. DISPARO DOS WEBHOOKS HTTP/TCP NO SEGUNDO EXATO ---
                if trig_http_seg_1 != -1 and tempo_restante == trig_http_seg_1 and not enviado_http_1:
                    enviado_http_1 = True
                    print(f"🚀 [DISPARO GATILHADO] H1 ativado nos {trig_http_seg_1}s!")
                    threading.Thread(target=executar_pedido_externo_assincrono,
                                     args=(trig_http_url_1, trig_http_met_1, {}, None), daemon=True).start()

                if trig_http_seg_2 != -1 and tempo_restante == trig_http_seg_2 and not enviado_http_2:
                    enviado_http_2 = True
                    threading.Thread(target=executar_pedido_externo_assincrono,
                                     args=(trig_http_url_2, trig_http_met_2, {}, None), daemon=True).start()

                if trig_http_seg_3 != -1 and tempo_restante == trig_http_seg_3 and not enviado_http_3:
                    enviado_http_3 = True
                    threading.Thread(target=executar_pedido_externo_assincrono,
                                     args=(trig_http_url_3, trig_http_met_3, {}, None), daemon=True).start()

                # --- 🧼 5. RE-ARMA DE GATILHOS (SÓ QUANDO O OPERADOR RESETAR PARA CIMA) ---
                if tempo_restante > gatilho_som_1: som_tocado_trig_1 = False
                if tempo_restante > gatilho_som_2: som_tocado_trig_2 = False
                if tempo_restante > gatilho_som_3: som_tocado_trig_3 = False
                if tempo_restante > trig_http_seg_1: enviado_http_1 = False
                if tempo_restante > trig_http_seg_2: enviado_http_2 = False
                if tempo_restante > trig_http_seg_3: enviado_http_3 = False

                # --- 6. MECANISMO DE PARAGEM EM ZERO ---
                if not modo_negativo and tempo_restante <= 0:
                    tempo_restante = 0
                    executando = False

                time.sleep(1.0)
            else:
                time.sleep(0.05)

        except Exception as e:
            print(f"[Loop Master] Erro assíncrono isolado: {e}")
            time.sleep(0.5)


CORES_FADE_IN_MSG = ["#000000", "#001a1c", "#003338", "#004d54", "#006670", "#00808c", "#0099a8", "#00b3bd", "#00ccd9",
                     "#00e6f5", "#3fd6ea"]
CORES_FADE_TIMER_OUT = ["#ffffff", "#e6e6e6", "#cccccc", "#b3b3b3", "#999999", "#808080", "#666666", "#4d4d4d",
                        "#333333", "#262626", "#222222"]


def animar_transicao_palco(passo=0):
    global mensagem_global, lbl_tempo_secundario, lbl_msg_secundaria, frame_conteudo_secundario
    if not janela_secundaria or not janela_secundaria.winfo_exists(): return
    tem_msg = bool(mensagem_global and mensagem_global.strip() != "")
    max_passos = len(CORES_FADE_IN_MSG) - 1

    if tem_msg:
        if passo == 0:
            lbl_tempo_secundario.config(font=(fonte_atual, int(90 * (ALTURA_ECRA / 1080.0)), "bold"))
            lbl_msg_secundaria.config(text=mensagem_global.upper(), fg="#000000")
            frame_conteudo_secundario.pack(fill="both", expand=True, pady=(20, 0))
        if passo <= max_passos:
            lbl_msg_secundaria.config(fg=CORES_FADE_IN_MSG[passo])
            if tempo_restante > (minutos_alerta * 60):
                lbl_tempo_secundario.config(fg=CORES_FADE_TIMER_OUT[passo])
            janela_secundaria.after(16, lambda: animar_transicao_palco(passo + 1))
    else:
        passo_inverso = max_passos - passo
        if passo_inverso >= 0:
            lbl_msg_secundaria.config(fg=CORES_FADE_IN_MSG[passo_inverso])
            if tempo_restante > (minutos_alerta * 60):
                lbl_tempo_secundario.config(fg=CORES_FADE_TIMER_OUT[passo_inverso])
            janela_secundaria.after(16, lambda: animar_transicao_palco(passo + 1))
        else:
            frame_conteudo_secundario.pack_forget()
            lbl_tempo_secundario.config(font=(fonte_atual, int(150 * (ALTURA_ECRA / 1080.0)), "bold"))
            lbl_tempo_secundario.pack(expand=True, pady=0)


def loop_atualizacao_ecran_nativo():
    """Gere o monitor de palco. Suprime as horas e pisca os números apenas se autorizado."""
    global tempo_restante, modo_visualizacao, mensagem_global, janela_secundaria, permitir_piscar_pos_zero
    global lbl_tempo_secundario, lbl_msg_secundaria, minutos_alerta, minutos_critico, estado_mensagem_anterior

    while True:
        try:
            if janela_secundaria and janela_secundaria.winfo_exists():
                janela_secundaria.after(0, lambda: janela_secundaria.configure(bg="#000000"))
                janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(bg="#000000"))
                janela_secundaria.after(0, lambda: frame_conteudo_secundario.configure(bg="#000000"))
                janela_secundaria.after(0, lambda: lbl_msg_secundaria.config(bg="#000000"))

                if modo_visualizacao == "relogio":
                    agora = datetime.datetime.now().strftime("%H:%M:%S")
                    janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(text=agora, fg="#3fd6ea"))
                else:
                    tempo_txt = formatar_tempo_completo(tempo_restante)

                    # --- LÓGICA DO PISCAR AUTÓNOMO GLOBAL (1 SEGUNDO DE SISTEMA) ---
                    if tempo_restante <= 0:
                        if permitir_piscar_pos_zero:
                            exibir_numeros = (int(time.time()) % 2 == 0)
                            if exibir_numeros:
                                janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(text=tempo_txt, fg="#ef4444"))
                            else:
                                janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(text=tempo_txt, fg="#000000"))
                        else:
                            janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(text=tempo_txt, fg="#ef4444"))
                    else:
                        janela_secundaria.after(0, lambda: lbl_tempo_secundario.config(text=tempo_txt))
                        if not (mensagem_global and mensagem_global.strip() != ""):
                            if tempo_restante <= (minutos_critico * 60):
                                cor = "#ef4444"
                            elif tempo_restante <= (minutos_alerta * 60):
                                cor = "#eab308"
                            else:
                                cor = "#ffffff"
                            janela_secundaria.after(0, lambda c=cor: lbl_tempo_secundario.config(fg=c))

                    if mensagem_global != estado_mensagem_anterior:
                        estado_mensagem_anterior = mensagem_global
                        janela_secundaria.after(0, lambda: animar_transicao_palco(0))
        except Exception:
            pass
        time.sleep(0.1)
# =========================================================================
# MOTORES DE REPRODUÇÃO DE ÁUDIO E FINALIZAÇÃO DE PROCESSOS NATIVOS
# =========================================================================
def rotina_minimizar_com_delay(caminho_vbs):
    """Aguarda o carregamento do player e força a minimização na barra de tarefas."""
    try:
        time.sleep(1.5)
        subprocess.Popen(["wscript", caminho_vbs], creationflags=0x08000000)
    except Exception:
        pass


def alterar_tamanho_fonte_local(direcao):
    """Altera o tamanho da fonte do palco via botões físicos do painel do operador."""
    global tamanho_fonte_timer_atual, lbl_tempo_secundario, fonte_atual, lbl_val_tamanho_ui
    try:
        if not 'tamanho_fonte_timer_atual' in globals():
            tamanho_fonte_timer_atual = 150

        if direcao == "plus":
            tamanho_fonte_timer_atual = min(400, tamanho_fonte_timer_atual + 10)
        else:
            tamanho_fonte_timer_atual = max(30, tamanho_fonte_timer_atual - 10)

        # 1. Atualiza o texto do indicador no próprio painel do operador
        if 'lbl_val_tamanho_ui' in globals() and lbl_val_tamanho_ui is not None:
            lbl_val_tamanho_ui.config(text=f"{tamanho_fonte_timer_atual}pt")

        # 2. Atualiza a janela de palco instantaneamente se ela estiver aberta
        if 'lbl_tempo_secundario' in globals() and lbl_tempo_secundario and lbl_tempo_secundario.winfo_exists():
            lbl_tempo_secundario.config(font=(fonte_atual, calcular_fonte(tamanho_fonte_timer_atual), "bold"))

        print(f"[Painel Local] Tamanho da fonte de palco alterado para: {tamanho_fonte_timer_atual}pt")
    except Exception:
        pass


# =========================================================================
# MOTORES DE REPRODUÇÃO DE ÁUDIO HÍBRIDOS (WINDOWS MCI / MAC AFPLAY v1.4)
# =========================================================================
def reproduzir_audio_nativo_invisivel(ficheiro_caminho):
    """Dispara o áudio de forma totalmente oculta em background (MCI no Win / afplay no Mac)."""
    try:
        caminho_absoluto = os.path.abspath(ficheiro_caminho)
        if os.path.exists(caminho_absoluto):
            parar_audio_nativo_sistema()

            if SISTEMA_MAC:
                # 🍎 No Mac: Usa o utilitário nativo afplay via subprocesso assíncrono
                subprocess.Popen(["afplay", caminho_absoluto], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[Áudio Mac] A reproduzir via afplay: {caminho_absoluto}")
            else:
                # 💻 No Windows: Continua a usar o teu motor MCI invisível por ctypes
                import ctypes
                ctypes.windll.winmm.mciSendStringW(f'open "{caminho_absoluto}" type mpegvideo alias som_regie', None, 0,
                                                   0)
                ctypes.windll.winmm.mciSendStringW('play som_regie', None, 0, 0)
                print(f"[Áudio Windows] A reproduzir via MCI: {caminho_absoluto}")
    except Exception as e:
        print(f"Erro no motor de áudio: {e}")


def tocar_som_background(num_gatilho=1):
    """Filtro de sons unificado. Executa bips nativos e ficheiros sem travar a GUI."""
    global som_ativado, som_selecionado_1, som_selecionado_2, som_selecionado_3

    # Se a variável global de mute estiver desativada, ignora o disparo
    if 'som_ativado' in globals() and not som_ativado:
        print(f"[Áudio Core] Som T{num_gatilho} ignorado (MUTE ativo).")
        return

    try:
        # Recupera o modo escrito na combobox correspondente
        if num_gatilho == 1:
            modo_som = som_selecionado_1 if 'som_selecionado_1' in globals() else "Beep"
        elif num_gatilho == 2:
            modo_som = som_selecionado_2 if 'som_selecionado_2' in globals() else "Beep"
        else:
            modo_som = som_selecionado_3 if 'som_selecionado_3' in globals() else "Beep"

        print(f"[Áudio Core] A processar disparo T{num_gatilho} em modo: {modo_som}")

        # Se for um ficheiro carregado pelo operador via botão BUSCAR
        if "Custom" in str(modo_som):
            caminho_wav = os.path.join(PASTA_DADOS_UTILIZADOR, f"alarme{num_gatilho}.wav")
            caminho_mp3 = os.path.join(PASTA_DADOS_UTILIZADOR, f"alarme{num_gatilho}.mp3")

            if os.path.exists(caminho_wav):
                reproduzir_audio_nativo_invisivel(caminho_wav)
            elif os.path.exists(caminho_mp3):
                reproduzir_audio_nativo_invisivel(caminho_mp3)
            else:
                # Fallback se o ficheiro custom sumiu da pasta do TIMER
                if not SISTEMA_MAC:
                    import winsound
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
                else:
                    os.system('echo -e "\a"')

        # 💥 CORREÇÃO DE ENGENHARIA: Valida tanto "Beep" (GUI) como "Bip" (Companion/Código)!
        elif modo_som in ["Beep", "Bip", "Alarme 1", "Alarme 2", "Sinal Horário", "Fim de Tempo"]:
            if SISTEMA_MAC:
                # 🍎 No Mac faz o bipe clássico de terminal
                os.system('echo -e "\a"')
            else:
                # 💻 No Windows faz o bipe eletrónico agudo de Régie através da motherboard
                import winsound
                winsound.Beep(1200, 300)

    except Exception as e:
        print(f"Erro ao disparar som T{num_gatilho}: {e}")


def parar_audio_nativo_sistema():
    """Para imediatamente qualquer reprodução de áudio ativa no sistema."""
    try:
        if SISTEMA_MAC:
            # 🍎 No Mac: Mata o processo do afplay instantaneamente
            subprocess.Popen(["killall", "afplay"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # 💻 No Windows: Limpa a memória MCI
            import ctypes
            ctypes.windll.winmm.mciSendStringW('stop som_regie', None, 0, 0)
            ctypes.windll.winmm.mciSendStringW('close som_regie', None, 0, 0)
    except Exception:
        pass


# Mapeamentos antigos de compatibilidade mantidos
def parar_mp3_janela_windows(): parar_audio_nativo_sistema()


def parar_audio_mci_windows(): parar_audio_nativo_sistema()


# =========================================================================
# FUNÇÕES DE INTERAÇÃO DOS BOTÕES E MECÂNICAS DA INTERFACE
# =========================================================================
def toggle_fullscreen_painel():
    """Alterna a janela principal entre ecrã inteiro e modo janela (80%) com moldura customizada."""
    global janela_fullscreen, btn_fullscreen, LARGURA_JANELA, ALTURA_JANELA, pos_x, pos_y

    if not janela_fullscreen:
        janela_fullscreen = True
        largura_total = janela_principal.winfo_screenwidth()
        altura_total = janela_principal.winfo_screenheight()
        janela_principal.geometry(f"{largura_total}x{altura_total}+0+0")
        if 'btn_fullscreen' in globals() and btn_fullscreen is not None:
            btn_fullscreen.config(text="🗗", fg="#eab308")
    else:
        janela_fullscreen = False
        janela_principal.geometry(f"{LARGURA_JANELA}x{ALTURA_JANELA}+{pos_x}+{pos_y}")
        if 'btn_fullscreen' in globals() and btn_fullscreen is not None:
            btn_fullscreen.config(text="🗖", fg="#34d399")


def alternar_modo_visualizacao():
    global modo_visualizacao, btn_alternar_web
    fonte_toggle = ("Arial", calcular_fonte(8), "bold")

    if modo_visualizacao == "timer":
        modo_visualizacao = "relogio"
        if 'btn_alternar_web' in globals() and btn_alternar_web is not None:
            btn_alternar_web.config(text="MUDAR PARA: MODO TIMER", bg="#0ea5c4", fg="#000000", font=fonte_toggle)
    else:
        modo_visualizacao = "timer"
        if 'btn_alternar_web' in globals() and btn_alternar_web is not None:
            btn_alternar_web.config(text="MUDAR PARA: MODO RELÓGIO", bg="#0e7490", fg="#dfe9ec", font=fonte_toggle)


def generar_janela_nativa_directx():
    """Garante que a janela abre fisicamente e já em Fullscreen no monitor externo do Mac sem passar pelo principal."""
    global janela_secundaria, lbl_tempo_secundario, lbl_msg_secundaria, frame_conteudo_secundario, tamanho_fonte_timer_atual, estado_mensagem_anterior
    if janela_secundaria and janela_secundaria.winfo_exists():
        janela_secundaria.lift()
        return

    janela_secundaria = Toplevel(root)
    janela_secundaria.title("Cue Timer Display")
    janela_secundaria.configure(bg="#000000")
    tamanho_fonte_timer_atual = 150
    estado_mensagem_anterior = ""

    LARGURA_PRINCIPAL = root.winfo_screenwidth()
    ALTURA_PRINCIPAL = root.winfo_screenheight()

    # Valores de segurança caso a deteção falhe
    monitor_alvo_x = LARGURA_PRINCIPAL
    monitor_alvo_y = 0
    largura_alvo = 1920
    altura_alvo = 1080
    tem_segundo_monitor = False

    try:
        import screeninfo
        monitores = screeninfo.get_monitors()
        if len(monitores) > 1:
            for m in monitores:
                # Caça o monitor secundário na Régie
                if m.x != 0 or m.is_primary == False:
                    monitor_alvo_x = m.x
                    monitor_alvo_y = m.y
                    largura_alvo = m.width
                    altura_alvo = m.height
                    tem_segundo_monitor = True
                    break
    except Exception:
        pass

    if SISTEMA_MAC:
        try:
            # 1. Isola o comportamento do espaço de trabalho (Auxiliary space 128)
            janela_secundaria.tk.call('wm', 'attributes', janela_secundaria._w, '-type', 'normal')
            janela_secundaria.tk.call('tk', 'mac', 'setWindowAttribute', janela_secundaria._w, 'collectionBehavior',
                                      '128')

            # 2. Força o posicionamento estrito ANTES de renderizar os gráficos
            janela_secundaria.geometry(f"{largura_alvo}x{altura_alvo}+{monitor_alvo_x}+{monitor_alvo_y}")

            # 3. Sincroniza o motor de janelas do Mac para ele processar a mudança de monitor
            janela_secundaria.update_idletasks()

            # 4. Só ativa o Fullscreen depois de a janela estar geograficamente no Monitor 2!
            if tem_segundo_monitor:
                janela_secundaria.wm_attributes("-fullscreen", True)
        except Exception:
            janela_secundaria.geometry(f"{largura_alvo}x{altura_alvo}+{monitor_alvo_x}+{monitor_alvo_y}")
    else:
        # Windows Direct-X Bypass clássico
        janela_secundaria.geometry(f"{largura_alvo}x{altura_alvo}+{monitor_alvo_x}+{monitor_alvo_y}")
        janela_secundaria.overrideredirect(True)

    janela_secundaria.bind("<Double-Button-1>", lambda e: fechar_ecran_nativo_botao())

    lbl_tempo_secundario = Label(janela_secundaria, text="00:00:00",
                                 font=(fonte_atual, calcular_fonte(140 if SISTEMA_MAC else 150), "bold"), bg="#000000",
                                 fg="#ffffff")
    lbl_tempo_secundario.pack(expand=True, pady=0)

    frame_conteudo_secundario = Frame(janela_secundaria, bg="#000000")
    lbl_msg_secundaria = Label(frame_conteudo_secundario, text="", font=(fonte_atual, calcular_fonte(55), "bold"),
                               bg="#000000", fg="#3fd6ea", wraplength=1200, justify="center")
    lbl_msg_secundaria.pack(expand=False, pady=20)


def fechar_ecran_nativo_botao():
    global janela_secundaria
    if janela_secundaria and janela_secundaria.winfo_exists():
        janela_secundaria.destroy()
        janela_secundaria = None


def toggle_modo_zero():
    global modo_negativo, btn_modo_zero
    modo_negativo = not modo_negativo
    if 'btn_modo_zero' in globals() and btn_modo_zero is not None:
        btn_modo_zero.config(text="MODO: CONTINUAR NEGATIVO" if modo_negativo else "MODO: PARAR NO ZERO",
                             bg="#0891b2" if modo_negativo else "#334155")


def aplicar_alertas_customizados():
    global minutos_alerta, minutes_critico, entry_alerta_amarelo, entry_alerta_vermelho
    try:
        if 'entry_alerta_amarelo' in globals() and entry_alerta_amarelo is not None:
            val_amarelo = entry_alerta_amarelo.get().strip()
            minutos_alerta = int(val_amarelo) if val_amarelo else 3
        if 'entry_alerta_vermelho' in globals() and entry_alerta_vermelho is not None:
            val_vermelho = entry_alerta_vermelho.get().strip()
            minutos_critico = int(val_vermelho) if val_vermelho else 1
    except Exception:
        minutos_alerta, minutos_critico = 3, 1





def executar_override_tempo():
    """Força o tempo digitado nas caixas a entrar em vigor e atualiza a memória de repetição."""
    global tempo_restante, tempo_inicial_memoria, lbl_status_tk
    try:
        hrs = int(entry_horas.get()) if entry_horas.get() else 0
        mins = int(entry_minutos.get()) if entry_minutos.get() else 0
        segs = int(entry_segundos.get()) if entry_segundos.get() else 0

        novo_tempo = (hrs * 3600) + (mins * 60) + segs
        tempo_restante = novo_tempo
        tempo_inicial_memoria = novo_tempo

        # 💥 CORREÇÃO DE ATUALIZAÇÃO: Altera o texto de forma limpa
        if 'lbl_status_tk' in globals() and lbl_status_tk and lbl_status_tk.winfo_exists():
            lbl_status_tk.config(text=formatar_tempo_completo(tempo_restante))

            # 🚀 TRANCA DE CAMADAS WINDOWS: Mantém o relógio na sua zona elástica
            # sem nunca o deixar colidir ou passar por cima do frame de botões do rodapé!
            lbl_status_tk.lift()

        if 'frame_botoes_acao' in globals() and frame_botoes_acao:
            frame_botoes_acao.lift()  # Obriga os 6 botões a saltarem para a frente de tudo

        if not SISTEMA_MAC and 'root' in globals() and root:
            root.update_idletasks()

        print(
            f"[Régie Override] Novo tempo de {formatar_tempo_completo(novo_tempo)} aplicado e gravado para repetições.")
    except Exception as e:
        print(f"[Erro Override] {e}")


# =========================================================================
# AJUSTES HORIZONTAIS, PRESETS DE TEMPO E CONTROLO DE MENSAGENS
# =========================================================================

# =========================================================================
# 🔕 MOTO DE RASCUNHO EXCLUSIVO: AJUSTE DE TEMPO SEM ATUALIZAÇÃO AUTOMÁTICA
# =========================================================================

def atualizar_tempo_por_inputs():
    """Garante que as alterações visuais nas caixas NÃO mexem no relógio se ele estiver a correr."""
    global tempo_restante, executando, entry_horas, entry_minutos, entry_segundos, lbl_status_tk, veio_de_stop_manual
    try:
        veio_de_stop_manual = False

        # 💥 A TRANCA OPERACIONAL: Se o cronómetro estiver ativo (a correr), ABORTA o auto-sincro!
        # O tempo modificado fica em rascunho na caixa e o relógio central continua imperturbável.
        if executando:
            return

        # Se o relógio estiver totalmente parado em repouso, atualiza o visor local normalmente
        hrs = int(entry_horas.get()) if entry_horas.get() else 0
        mins = int(entry_minutos.get()) if entry_minutos.get() else 0
        segs = int(entry_segundos.get()) if entry_segundos.get() else 0
        tempo_restante = (hrs * 3600) + (mins * 60) + segs

        if 'lbl_status_tk' in globals() and lbl_status_tk and lbl_status_tk.winfo_exists():
            lbl_status_tk.config(text=formatar_tempo_completo(tempo_restante))
    except Exception:
        pass


def alterar_horas(q):
    """Soma ou subtrai horas apenas na caixa de texto visual, aguardando confirmação."""
    global entry_horas, entry_minutos, entry_segundos
    try:
        h = int(entry_horas.get()) if entry_horas.get() else 0
        m = int(entry_minutos.get()) if entry_minutos.get() else 0
        s = int(entry_segundos.get()) if entry_segundos.get() else 0
        tot = max(0, (h * 3600) + (m * 60) + s + (q * 3600))

        entry_horas.delete(0, 'end')
        entry_horas.insert(0, f"{tot // 3600:02d}")
        entry_minutos.delete(0, 'end')
        entry_minutos.insert(0, f"{(tot % 3600) // 60:02d}")
        entry_segundos.delete(0, 'end')
        entry_segundos.insert(0, f"{tot % 60:02d}")

        # 💥 Pura injeção visual: Atualiza as tarefas do Tkinter sem chamar overrides automáticos
        if 'root' in globals() and root:
            root.update_idletasks()
    except Exception:
        pass


def alterar_minutos(q):
    """Soma ou subtrai minutos apenas na caixa de texto visual, aguardando confirmação."""
    global entry_horas, entry_minutos, entry_segundos
    try:
        h = int(entry_horas.get()) if entry_horas.get() else 0
        m = int(entry_minutos.get()) if entry_minutos.get() else 0
        s = int(entry_segundos.get()) if entry_segundos.get() else 0
        tot = max(0, (h * 3600) + (m * 60) + s + (q * 60))

        entry_horas.delete(0, 'end')
        entry_horas.insert(0, f"{tot // 3600:02d}")
        entry_minutos.delete(0, 'end')
        entry_minutos.insert(0, f"{(tot % 3600) // 60:02d}")
        entry_segundos.delete(0, 'end')
        entry_segundos.insert(0, f"{tot % 60:02d}")

        if 'root' in globals() and root:
            root.update_idletasks()
    except Exception:
        pass


def alterar_segundos(q):
    """Soma ou subtrai segundos apenas na caixa de texto visual, aguardando confirmação."""
    global entry_horas, entry_minutos, entry_segundos
    try:
        h = int(entry_horas.get()) if entry_horas.get() else 0
        m = int(entry_minutos.get()) if entry_minutos.get() else 0
        s = int(entry_segundos.get()) if entry_segundos.get() else 0
        tot = max(0, (h * 3600) + (m * 60) + s + q)

        entry_horas.delete(0, 'end')
        entry_horas.insert(0, f"{tot // 3600:02d}")
        entry_minutos.delete(0, 'end')
        entry_minutos.insert(0, f"{(tot % 3600) // 60:02d}")
        entry_segundos.delete(0, 'end')
        entry_segundos.insert(0, f"{tot % 60:02d}")

        if 'root' in globals() and root:
            root.update_idletasks()
    except Exception:
        pass


def atualizar_campo_mensagem_ui(texto):
    try:
        if 'entry_mensagem' in globals() and entry_mensagem is not None:
            entry_mensagem.delete(0, 'end')
            entry_mensagem.insert(0, texto)
    except Exception: pass

def aplicar_preset_index(index):
    global tempo_restante, executando, entry_horas, entry_minutos, entry_segundos, lbl_status_tk
    if not executando:
        try:
            segundos_totais = valores_presets[index]
            hrs = segundos_totais // 3600
            mins = (segundos_totais % 3600) // 60
            segs = segundos_totais % 60
            entry_horas.delete(0, 'end')
            entry_horas.insert(0, f"{hrs:02d}")
            entry_minutos.delete(0, 'end')
            entry_minutos.insert(0, f"{mins:02d}")
            entry_segundos.delete(0, 'end')
            entry_segundos.insert(0, f"{segs:02d}")
            tempo_restante = segundos_totais
            if lbl_status_tk: lbl_status_tk.set(f"Tempo: {formatar_tempo_completo(tempo_restante)}")
        except Exception: pass


def capturar_preset_msg(idx):
    """Captura o texto escrito na entry_mensagem e grava no slot selecionado (0 a 9)."""
    global textos_presets_msg, botoes_msg_referencias
    try:
        if 'entry_mensagem' in globals() and entry_mensagem:
            texto_digitado = entry_mensagem.get().strip()
            if not texto_digitado:
                return

            # Grava no slot correto da memória RAM
            textos_presets_msg[idx] = texto_digitado

            # Atualiza o texto do botão inferior correspondente e auto-ajusta a fonte
            if idx < len(botoes_msg_referencias):
                botao_alvo = botoes_msg_referencias[idx]
                # Usa o nome exato da tua função de estilo do bloco anterior
                if 'atualizar_estilo_botao_msg' in globals():
                    atualizar_estilo_botao_msg(botao_alvo, texto_digitado)
                elif 'atualizar_style_botao_msg' in globals():
                    atualizar_style_botao_msg(botao_alvo, texto_digitado)

                print(f"[Régie Texto] Mensagem salva no Slot M{idx + 1}: {texto_digitado}")
    except Exception as e:
        print(f"[Erro M-SET] Falha ao capturar mensagem {idx}: {e}")


def enviar_mensagem_ecra(texto_forçado=None):
    """Lê a caixa de texto ou aceita um bypass direto em memória para disparar sem micro-atrasos."""
    global mensagem_global

    # 💥 BYPASS COMPANION/PRESET: Se enviarmos o texto direto da memória, usamos o valor sem ler a GUI!
    if texto_forçado is not None:
        mensagem_global = texto_forçado
    elif 'entry_mensagem' in globals() and entry_mensagem is not None:
        mensagem_global = entry_mensagem.get()

    if 'root' in globals() and root:
        root.after(0, animar_transicao_palco)


def limpar_mensagem_ecra():
    """Limpa a variável de broadcast e esvazia a caixa visível do ecrã."""
    global mensagem_global
    mensagem_global = ""
    if 'entry_mensagem' in globals() and entry_mensagem is not None:
        entry_mensagem.delete(0, 'end')
    if 'root' in globals() and root:
        root.after(0, animar_transicao_palco)


def disparar_preset_msg(idx):
    """Resgata a mensagem, atualiza o painel e força o envio direto via bypass de memória."""
    global textos_presets_msg, mensagem_global, estado_mensagem_anterior
    try:
        mensagem_final = textos_presets_msg[idx]

        # 1. Sincroniza as variáveis clássicas de estúdio
        mensagem_global = mensagem_final
        estado_mensagem_anterior = mensagem_final

        # 2. Atualiza a caixa visível no ecrã para o operador saber o que está ativo
        if 'entry_mensagem' in globals() and entry_mensagem:
            entry_mensagem.delete(0, "end")
            entry_mensagem.insert(0, mensagem_final)

        # 3. 🚀 DISPARO EM BROADCAST COM BYPASS: Passamos a string em punho para quebrar o atraso do .get()!
        if 'enviar_mensagem_ecra' in globals():
            enviar_mensagem_ecra(texto_forçado=mensagem_final)
            print(f"[Régie Texto] Mensagem M{idx + 1} DISPARADA à velocidade da luz: {mensagem_final}")
    except Exception as e:
        print(f"[Erro Disparo Msg] Falha ao enviar preset {idx}: {e}")


# =========================================================================
# TRANCAS DO CRONÓMETRO, MUTE, SINCRONIZADORES E CONTROLOS DE FONTE
# =========================================================================
def iniciar_timer():
    """Lê o tempo das caixas, atualiza os triggers e força o arranque do relógio."""
    global tempo_restante, executando, veio_de_stop_manual, tempo_inicial_memoria, lbl_status_tk, lbl_preview_regie_tk
    try:
        if 'aplicar_alertas_customizados' in globals():
            aplicar_alertas_customizados()

        # 💥 INJEÇÃO OBRIGATÓRIA: Força o Python a ler as caixas H1, H2, H3 antes de ligar o motor!
        if 'atualizar_gatilhos_http_via_painel' in globals():
            atualizar_gatilhos_http_via_painel()

        veio_de_stop_manual = False

        h = int(entry_horas.get()) if 'entry_horas' in globals() and entry_horas.get().strip() else 0
        m = int(entry_minutos.get()) if 'entry_minutos' in globals() and entry_minutos.get().strip() else 0
        s = int(entry_segundos.get()) if 'entry_segundos' in globals() and entry_segundos.get().strip() else 0

        tempo_restante = (h * 3600) + (m * 60) + s
        tempo_inicial_memoria = tempo_restante

        executando = True

        # 💥 SYNC EM DUPLO CANAL: Acorda o ecrã de palco e o teu novo visor digital da Régie em simultâneo!
        txt_formatado = formatar_tempo_completo(tempo_restante)
        if 'lbl_status_tk' in globals() and lbl_status_tk:
            lbl_status_tk.set(f"Tempo: {txt_formatado}")

        if 'lbl_preview_regie_tk' in globals() and lbl_preview_regie_tk:
            lbl_preview_regie_tk.set(f"Tempo: {txt_formatado}")

        print(f"[Régie Core] INICIAR: Contagem ativa para {txt_formatado}.")
    except Exception as e:
        print(f"Erro ao iniciar o cronómetro: {str(e)}")


def pausar_timer():
    global executando
    executando = False
    parar_mp3_janela_windows()


def parar_timer():
    """Para o temporizador, zera o relógio e silencia o motor de áudio invisível."""
    global tempo_restante, executando, lbl_status_tk, veio_de_stop_manual
    executando = False
    veio_de_stop_manual = True
    tempo_restante = 0

    parar_audio_mci_windows()  # 👈 Atualizado para desligar o canal MCI invisível

    if lbl_status_tk:
        lbl_status_tk.set("Tempo: 00:00:00")


def reset_timer_local():
    """Sequência Broadcast: PAUSE -> RESET TO TIME (Apenas atualiza caixas e limpa trincos para o Companion)."""
    global tempo_restante, tempo_inicial_memoria, executando, lbl_status_tk
    global veio_de_stop_manual
    global som_tocado_trig_1, som_tocado_trig_2, som_tocado_trig_3
    global enviado_http_1, enviado_http_2, enviado_http_3
    try:
        # 1. Trava o motor para a injeção assentar limpa
        executando = False
        veio_de_stop_manual = False

        # 2. Resgata o último tempo carregado em memória antes do arranque
        tempo_restante = tempo_inicial_memoria

        # 3. Converte segundos para HH:MM:SS e injeta fisicamente nas caixas do ecrã
        h = tempo_restante // 3600
        m = (tempo_restante % 3600) // 60
        s = tempo_restante % 60

        if 'entry_horas' in globals() and entry_horas:
            entry_horas.delete(0, "end");
            entry_horas.insert(0, str(h))
        if 'entry_minutos' in globals() and entry_minutos:
            entry_minutos.delete(0, "end");
            entry_minutos.insert(0, str(m))
        if 'entry_segundos' in globals() and entry_segundos:
            entry_segundos.delete(0, "end");
            entry_segundos.insert(0, str(s))

        # 4. Sincroniza o relógio gigante local
        if 'lbl_status_tk' in globals() and lbl_status_tk:
            lbl_status_tk.set(f"Tempo: {formatar_tempo_completo(tempo_restante)}")

        # 5. 🧼 REPARAÇÃO GATILHOS: Liberta todos os trincos para os GETs e alarmes poderem disparar de novo!
        som_tocado_trig_1 = False;
        som_tocado_trig_2 = False;
        som_tocado_trig_3 = False
        enviado_http_1 = False;
        enviado_http_2 = False;
        enviado_http_3 = False

        if 'aplicar_alertas_customizados' in globals():
            aplicar_alertas_customizados()

        if 'root' in globals() and root:
            root.update_idletasks()

        print(f"[Régie] RESET Concluído: Caixas repostas para {h:02d}:{m:02d}:{s:02d}. Trincos livres.")
    except Exception as e:
        print(f"Erro no reset local: {str(e)}")


def reiniciar_timer():
    """Sequência Automática: PAUSE -> RESET TO TIME -> PLAY (Bypass total à leitura de zeros da GUI)."""
    global tempo_restante, tempo_inicial_memoria, executando, lbl_status_tk
    global veio_de_stop_manual
    global som_tocado_trig_1, som_tocado_trig_2, som_tocado_trig_3
    global enviado_http_1, enviado_http_2, enviado_http_3
    try:
        # 1. Pausa ciclos residuais
        executando = False
        time.sleep(0.02)
        veio_de_stop_manual = False

        # 2. Injeta o tempo original direto na memória do Python
        tempo_restante = tempo_inicial_memoria

        # 3. Atualiza as caixas Entry visuais para o operador ver a mudança
        h = tempo_restante // 3600
        m = (tempo_restante % 3600) // 60
        s = tempo_restante % 60

        if 'entry_horas' in globals() and entry_horas:
            entry_horas.delete(0, "end");
            entry_horas.insert(0, str(h))
        if 'entry_minutos' in globals() and entry_minutos:
            entry_minutos.delete(0, "end");
            entry_minutos.insert(0, str(m))
        if 'entry_segundos' in globals() and entry_segundos:
            entry_segundos.delete(0, "end");
            entry_segundos.insert(0, str(s))

        if 'lbl_status_tk' in globals() and lbl_status_tk:
            lbl_status_tk.set(f"Tempo: {formatar_tempo_completo(tempo_restante)}")

        # 4. Limpa rigorosamente os trincos para a nova contagem correr direita
        som_tocado_trig_1 = False;
        som_tocado_trig_2 = False;
        som_tocado_trig_3 = False
        enviado_http_1 = False;
        enviado_http_2 = False;
        enviado_http_3 = False

        if 'aplicar_alertas_customizados' in globals():
            aplicar_alertas_customizados()

        # 5. 🚀 DISPARO DIRETO: Força a flag de execução sem passar pela leitura do iniciar_timer()
        executando = True

        if 'root' in globals() and root:
            root.update_idletasks()

        print(f"[Régie] REINICIAR: Motor disparado com sucesso para {formatar_tempo_completo(tempo_restante)}.")
    except Exception as e:
        print(f"Erro no reiniciar automático: {str(e)}")


# =========================================================================
# MOTOR DA LISTA DE CUES: NEXT MANUAL + GATILHO AUTOMÁTICO DE SLIDES
# =========================================================================
def aplicar_cue(indice, autostart=True):
    """Carrega o tempo da cue indicada no cronómetro e, por omissão, arranca a contagem de imediato.
    Deve ser chamada sempre a partir da thread principal do Tkinter (via root.after)."""
    global tempo_restante, tempo_inicial_memoria, executando, indice_cue_atual, veio_de_stop_manual
    global som_tocado_trig_1, som_tocado_trig_2, som_tocado_trig_3
    global enviado_http_1, enviado_http_2, enviado_http_3
    try:
        if indice < 0 or indice >= len(lista_cues):
            return
        cue = lista_cues[indice]
        indice_cue_atual = indice

        executando = False
        veio_de_stop_manual = False

        tempo_restante = max(0, int(cue.get("tempo", 0)))
        tempo_inicial_memoria = tempo_restante

        h = tempo_restante // 3600
        m = (tempo_restante % 3600) // 60
        s = tempo_restante % 60
        if 'entry_horas' in globals() and entry_horas:
            entry_horas.delete(0, "end"); entry_horas.insert(0, str(h))
        if 'entry_minutos' in globals() and entry_minutos:
            entry_minutos.delete(0, "end"); entry_minutos.insert(0, str(m))
        if 'entry_segundos' in globals() and entry_segundos:
            entry_segundos.delete(0, "end"); entry_segundos.insert(0, str(s))
        if 'lbl_status_tk' in globals() and lbl_status_tk:
            lbl_status_tk.set(f"Tempo: {formatar_tempo_completo(tempo_restante)}")

        # Liberta os trincos de alarmes/webhooks para poderem disparar de novo nesta cue
        som_tocado_trig_1 = som_tocado_trig_2 = som_tocado_trig_3 = False
        enviado_http_1 = enviado_http_2 = enviado_http_3 = False

        if 'aplicar_alertas_customizados' in globals():
            aplicar_alertas_customizados()

        if autostart:
            executando = True

        if 'atualizar_janela_cues_lista' in globals():
            atualizar_janela_cues_lista()

        print(f"[Cue List] Cue #{indice + 1} aplicada -> slide {cue.get('slide')}, {formatar_tempo_completo(tempo_restante)}.")
    except Exception as e:
        print(f"[Cue List] Erro ao aplicar cue #{indice + 1}: {e}")


def avancar_cue_next():
    """Avança manualmente para a cue seguinte da lista (botão NEXT no painel ou via Companion)."""
    global indice_cue_atual
    if not lista_cues:
        print("[Cue List] Lista vazia — nada para avançar.")
        return
    proximo = indice_cue_atual + 1
    if proximo >= len(lista_cues):
        print("[Cue List] Já estás na última cue da lista.")
        return
    root.after(0, lambda: aplicar_cue(proximo))


def ir_para_cue_por_slide(numero_slide):
    """Procura a cue cujo número de slide corresponde ao slide atual e aplica-a.
    Chamada pela thread de deteção automática — despacha para a thread principal."""
    for i, cue in enumerate(lista_cues):
        try:
            if int(cue.get("slide", -1)) == int(numero_slide):
                root.after(0, lambda idx=i: aplicar_cue(idx, autostart=True))
                return True
        except (TypeError, ValueError):
            continue
    return False


def detetar_slide_powerpoint():
    """Lê o número do slide atual de uma apresentação em curso no PowerPoint (Windows, via COM).
    Devolve None se o PowerPoint não estiver aberto ou não estiver a apresentar."""
    try:
        import win32com.client
        aplicacao_ppt = win32com.client.GetActiveObject("PowerPoint.Application")
        if aplicacao_ppt.SlideShowWindows.Count > 0:
            return int(aplicacao_ppt.SlideShowWindows(1).View.CurrentShowPosition)
    except Exception:
        pass
    return None


def detetar_slide_keynote():
    """Lê o número do slide atual de uma apresentação em curso no Keynote (macOS, via AppleScript).
    Devolve None se o Keynote não estiver aberto ou não estiver a apresentar."""
    try:
        script_presente = 'tell application "System Events" to (name of processes) contains "Keynote"'
        resultado = subprocess.run(["osascript", "-e", script_presente], capture_output=True, text=True, timeout=1.5)
        if "true" not in resultado.stdout.strip().lower():
            return None

        script_slide = ('tell application "Keynote" to if playing then '
                         'return slide number of current slide of front document')
        resultado = subprocess.run(["osascript", "-e", script_slide], capture_output=True, text=True, timeout=1.5)
        saida = resultado.stdout.strip()
        if saida.isdigit():
            return int(saida)
    except Exception:
        pass
    return None


def atualizar_botao_deteccao_ui():
    """Sincroniza o botão e o estado visual da deteção automática no painel de cues."""
    try:
        if 'btn_toggle_deteccao' in globals() and btn_toggle_deteccao is not None and btn_toggle_deteccao.winfo_exists():
            btn_toggle_deteccao.set_estado(
                ativo=deteccao_automatica_ativa,
                texto="🟢 DETEÇÃO AUTOMÁTICA: LIGADA" if deteccao_automatica_ativa else "⚪ DETEÇÃO AUTOMÁTICA: DESLIGADA"
            )
    except Exception:
        pass


def toggle_deteccao_automatica():
    """Liga/desliga a vigilância automática do PowerPoint/Keynote a partir do botão no painel de cues."""
    global deteccao_automatica_ativa, ultimo_slide_detectado
    deteccao_automatica_ativa = not deteccao_automatica_ativa
    ultimo_slide_detectado = None
    atualizar_botao_deteccao_ui()
    print(f"[Cue List] Deteção automática de slides: {'LIGADA' if deteccao_automatica_ativa else 'DESLIGADA'}.")


def loop_deteccao_slides():
    """Vigia em background o slide atual do PowerPoint (Windows) ou Keynote (Mac) e dispara
    automaticamente a cue correspondente assim que o operador muda de slide na apresentação."""
    global ultimo_slide_detectado
    while True:
        try:
            if deteccao_automatica_ativa and lista_cues:
                slide_atual = detetar_slide_keynote() if SISTEMA_MAC else detetar_slide_powerpoint()

                if slide_atual is not None and slide_atual != ultimo_slide_detectado:
                    ultimo_slide_detectado = slide_atual
                    encontrou = ir_para_cue_por_slide(slide_atual)
                    if 'lbl_deteccao_status' in globals() and lbl_deteccao_status:
                        texto = f"Slide atual: {slide_atual}" + ("" if encontrou else " (sem cue associada)")
                        root.after(0, lambda t=texto: lbl_deteccao_status.config(text=t, fg="#34d399"))
                elif slide_atual is None and ultimo_slide_detectado is not None:
                    ultimo_slide_detectado = None
                    if 'lbl_deteccao_status' in globals() and lbl_deteccao_status:
                        root.after(0, lambda: lbl_deteccao_status.config(text="Sem apresentação ativa...", fg="#eab308"))
        except Exception as e:
            print(f"[Deteção Slides] Erro assíncrono isolado: {e}")
        time.sleep(0.4)


def atualizar_janela_cues_lista():
    """Redesenha a listbox de cues, destacando qual está ativa neste momento."""
    if 'listbox_cues' not in globals() or listbox_cues is None or not listbox_cues.winfo_exists():
        return
    try:
        selecao_anterior = listbox_cues.curselection()
        listbox_cues.delete(0, "end")
        for i, cue in enumerate(lista_cues):
            marcador = "▶ " if i == indice_cue_atual else "   "
            linha = (f"{marcador}#{i + 1}  Slide {cue.get('slide')}  ·  "
                     f"{formatar_tempo_completo(int(cue.get('tempo', 0)))}  ·  {cue.get('nome', '')}")
            listbox_cues.insert("end", linha)
            listbox_cues.itemconfig(i, fg="#34d399" if i == indice_cue_atual else "#dfe9ec")
        if selecao_anterior:
            listbox_cues.selection_set(selecao_anterior[0])
    except Exception:
        pass


def adicionar_cue():
    """Lê o formulário da janela de cues e acrescenta uma nova cue no fim da lista."""
    global lista_cues
    try:
        slide_txt = entry_cue_slide.get().strip()
        tempo_txt = entry_cue_tempo.get().strip()
        nome_txt = entry_cue_nome.get().strip()

        if not slide_txt.isdigit():
            messagebox.showwarning("Cue inválida", "Indica um número de slide válido.")
            return

        tempo_segs = converter_string_tempo_para_segundos(tempo_txt)
        if tempo_segs < 0:
            messagebox.showwarning("Cue inválida", "Indica um tempo válido (ex: 02:00 ou 90).")
            return

        lista_cues.append({
            "slide": int(slide_txt),
            "tempo": tempo_segs,
            "nome": nome_txt or f"Cue {len(lista_cues) + 1}"
        })
        gravar_lista_cues()
        atualizar_janela_cues_lista()

        entry_cue_slide.delete(0, "end")
        entry_cue_tempo.delete(0, "end")
        entry_cue_nome.delete(0, "end")
        entry_cue_slide.focus_set()
    except Exception as e:
        print(f"[Cue List] Erro ao adicionar cue: {e}")


def remover_cue_selecionada():
    """Remove a cue selecionada na listbox, reajustando o índice da cue ativa se necessário."""
    global lista_cues, indice_cue_atual
    try:
        selecao = listbox_cues.curselection()
        if not selecao:
            return
        idx = selecao[0]
        del lista_cues[idx]
        if indice_cue_atual == idx:
            indice_cue_atual = -1
        elif indice_cue_atual > idx:
            indice_cue_atual -= 1
        gravar_lista_cues()
        atualizar_janela_cues_lista()
    except Exception as e:
        print(f"[Cue List] Erro ao remover cue: {e}")


def mover_cue(direcao):
    """Troca a cue selecionada de posição com a vizinha (direcao=-1 sobe, +1 desce)."""
    global lista_cues, indice_cue_atual
    try:
        selecao = listbox_cues.curselection()
        if not selecao:
            return
        idx = selecao[0]
        novo_idx = idx + direcao
        if novo_idx < 0 or novo_idx >= len(lista_cues):
            return
        lista_cues[idx], lista_cues[novo_idx] = lista_cues[novo_idx], lista_cues[idx]
        if indice_cue_atual == idx:
            indice_cue_atual = novo_idx
        elif indice_cue_atual == novo_idx:
            indice_cue_atual = idx
        gravar_lista_cues()
        atualizar_janela_cues_lista()
        listbox_cues.selection_set(novo_idx)
    except Exception as e:
        print(f"[Cue List] Erro ao mover cue: {e}")


def abrir_janela_cues():
    """Abre (ou traz para a frente) o painel de gestão da Lista de Cues."""
    global janela_cues, listbox_cues, entry_cue_slide, entry_cue_tempo, entry_cue_nome
    global lbl_deteccao_status, btn_toggle_deteccao

    if janela_cues and janela_cues.winfo_exists():
        janela_cues.lift()
        return

    janela_cues = Toplevel(root)
    janela_cues.title("Cue Timer — Lista de Cues")
    janela_cues.configure(bg="#0b0f1a")
    janela_cues.geometry("560x640")

    fonte_lbl = ("Arial", calcular_fonte(9), "bold")
    fonte_entry = ("Arial", calcular_fonte(10))

    frame_form = Frame(janela_cues, bg="#0b0f1a")
    frame_form.pack(fill="x", padx=14, pady=(14, 6))
    frame_form.columnconfigure(2, weight=1)

    Label(frame_form, text="Slide Nº", font=fonte_lbl, bg="#0b0f1a", fg="#dfe9ec").grid(row=0, column=0, sticky="w")
    entry_cue_slide = Entry(frame_form, font=fonte_entry, width=6, justify="center")
    entry_cue_slide.grid(row=1, column=0, padx=(0, 8), pady=(2, 8))

    Label(frame_form, text="Tempo (mm:ss)", font=fonte_lbl, bg="#0b0f1a", fg="#dfe9ec").grid(row=0, column=1, sticky="w")
    entry_cue_tempo = Entry(frame_form, font=fonte_entry, width=8, justify="center")
    entry_cue_tempo.grid(row=1, column=1, padx=(0, 8), pady=(2, 8))

    Label(frame_form, text="Nome da Cue", font=fonte_lbl, bg="#0b0f1a", fg="#dfe9ec").grid(row=0, column=2, sticky="w")
    entry_cue_nome = Entry(frame_form, font=fonte_entry)
    entry_cue_nome.grid(row=1, column=2, padx=(0, 8), pady=(2, 8), sticky="ew")

    Button(frame_form, text="+ ADICIONAR", bg="#0d9488", fg="white", font=fonte_lbl, bd=0,
           command=adicionar_cue).grid(row=1, column=3, ipady=6, sticky="ew")

    listbox_cues = Listbox(janela_cues, font=("Consolas", calcular_fonte(10)), bg="#0d1220", fg="#dfe9ec",
                            selectbackground="#0ea5c4", activestyle="none", height=14, bd=0, highlightthickness=0)
    listbox_cues.pack(fill="both", expand=True, padx=14, pady=6)

    frame_gestao = Frame(janela_cues, bg="#0b0f1a")
    frame_gestao.pack(fill="x", padx=14, pady=(0, 6))
    frame_gestao.columnconfigure((0, 1, 2), weight=1)
    Button(frame_gestao, text="▲ SUBIR", bg="#374151", fg="white", font=fonte_lbl, bd=0,
           command=lambda: mover_cue(-1)).grid(row=0, column=0, padx=3, ipady=4, sticky="ew")
    Button(frame_gestao, text="▼ DESCER", bg="#374151", fg="white", font=fonte_lbl, bd=0,
           command=lambda: mover_cue(1)).grid(row=0, column=1, padx=3, ipady=4, sticky="ew")
    Button(frame_gestao, text="🗑 REMOVER", bg="#b91c1c", fg="white", font=fonte_lbl, bd=0,
           command=remover_cue_selecionada).grid(row=0, column=2, padx=3, ipady=4, sticky="ew")

    Button(janela_cues, text="▶ NEXT — aplica e arranca a cue seguinte", bg="#0ea5c4", fg="white",
           font=("Arial", calcular_fonte(12), "bold"), bd=0, command=avancar_cue_next
           ).pack(fill="x", padx=14, pady=(6, 10), ipady=10)

    Label(janela_cues, text="―" * 60, bg="#0b0f1a", fg="#1f2937").pack()

    nome_app_deteccao = "Keynote" if SISTEMA_MAC else "PowerPoint"
    btn_toggle_deteccao = BotaoMetal(
        janela_cues,
        text="🟢 DETEÇÃO AUTOMÁTICA: LIGADA" if deteccao_automatica_ativa else "⚪ DETEÇÃO AUTOMÁTICA: DESLIGADA",
        ativo=deteccao_automatica_ativa, raio=10, fonte=fonte_lbl,
        height=calcular_fonte(30), bg_pai="#0b0f1a", command=toggle_deteccao_automatica
    )
    btn_toggle_deteccao.pack(fill="x", padx=14, pady=(10, 4))

    lbl_deteccao_status = Label(
        janela_cues, text=f"Vigia o {nome_app_deteccao} enquanto a apresentação está a decorrer.",
        font=("Arial", calcular_fonte(8)), bg="#0b0f1a", fg="#7d97a3", wraplength=520, justify="center"
    )
    lbl_deteccao_status.pack(pady=(0, 12))

    atualizar_janela_cues_lista()


def toggle_mute_som():
    global som_ativado, btn_mute_som
    som_ativado = not som_ativado
    if 'btn_mute_som' in globals() and btn_mute_som is not None:
        btn_mute_som.set_estado(ativo=som_ativado,
                                texto="🔊 SOM: ON" if som_ativado else "🔇 SOM: MUTADO")


def toggle_permissao_piscar():
    global permitir_piscar_pos_zero, btn_toggle_piscar
    permitir_piscar_pos_zero = not permitir_piscar_pos_zero
    if 'btn_toggle_piscar' in globals() and btn_toggle_piscar is not None:
        btn_toggle_piscar.set_estado(
            ativo=permitir_piscar_pos_zero,
            texto="💥 PISCAR: LIGADO" if permitir_piscar_pos_zero else "🛑 PISCAR: DESLIGADO"
        )


def converter_string_tempo_para_segundos(texto_tempo):
    """Tradução matemática broadcast: Converte HH:MM:SS, MM:SS ou SS para segundos puros."""
    if not texto_tempo:
        return -1
    try:
        texto_limpo = str(texto_tempo).strip().replace(" ", "")
        if not texto_limpo:
            return -1

        # Se forem segundos puros (ex: "80")
        if ":" not in texto_limpo:
            if texto_limpo.isdigit():
                return int(texto_limpo)
            return -1

        partes = texto_limpo.split(":")

        # 💥 CORREÇÃO MATEMÁTICA REAL: Usar os índices corretos [0] e [1] do array!
        if len(partes) == 2:
            minutos = int(partes[0]) if partes[0].isdigit() else 0
            segundos = int(partes[1]) if partes[1].isdigit() else 0
            return (minutos * 60) + segundos

        # Formato HH:MM:SS (ex: "01:00:00")
        elif len(partes) == 3:
            horas = int(partes[0]) if partes[0].isdigit() else 0
            minutos = int(partes[1]) if partes[1].isdigit() else 0
            segundos = int(partes[2]) if partes[2].isdigit() else 0
            return (horas * 3600) + (minutos * 60) + segundos

    except Exception as e:
        print(f"[Conversor] Erro crítico na conversão: {e}")
    return -1


def atualizar_gatilhos_http_via_painel():
    """Lê as caixas de texto de automação, extrai os segundos com o conversor e atualiza a memória."""
    global trig_http_seg_1, trig_http_url_1, trig_http_met_1
    global trig_http_seg_2, trig_http_url_2, trig_http_met_2
    global trig_http_seg_3, trig_http_url_3, trig_http_met_3

    def extrair_tempo_seguro(entry_obj, valor_atual):
        if not entry_obj: return valor_atual
        texto = entry_obj.get().strip()
        # Se a caixa já tiver o texto de telemetria "Falta", NÃO esmagamos o valor real da memória!
        if "Falta" in texto:
            return valor_atual
        res = converter_string_tempo_para_segundos(texto)
        return res if res >= 0 else valor_atual

    try:
        if 'entry_http_seg1' in globals() and entry_http_seg1:
            trig_http_seg_1 = extrair_tempo_seguro(entry_http_seg1, trig_http_seg_1)
        if 'entry_http_url1' in globals() and entry_http_url1:
            url_texto = entry_http_url1.get().strip()
            if url_texto and "http" in url_texto:
                trig_http_url_1 = url_texto
        if 'seletor_http_met1' in globals() and seletor_http_met1:
            trig_http_met_1 = seletor_http_met1.get()

        if 'entry_http_seg2' in globals() and entry_http_seg2:
            trig_http_seg_2 = extrair_tempo_seguro(entry_http_seg2, trig_http_seg_2)
        if 'entry_http_url2' in globals() and entry_http_url2:
            url_texto = entry_http_url2.get().strip()
            if url_texto and "http" in url_texto: trig_http_url_2 = url_texto
        if 'seletor_http_met2' in globals() and seletor_http_met2:
            trig_http_met_2 = seletor_http_met2.get()

        if 'entry_http_seg3' in globals() and entry_http_seg3:
            trig_http_seg_3 = extrair_tempo_seguro(entry_http_seg3, trig_http_seg_3)
        if 'entry_http_url3' in globals() and entry_http_url3:
            url_texto = entry_http_url3.get().strip()
            if url_texto and "http" in url_texto: trig_http_url_3 = url_texto
        if 'seletor_http_met3' in globals() and seletor_http_met3:
            trig_http_met_3 = seletor_http_met3.get()
    except Exception:
        pass


def armar_gatilho_h_direto(num_canal):
    """Guarda rigorosamente o tempo em segundos na memória da thread de background."""
    global trig_http_seg_1, trig_http_seg_2, trig_http_seg_3
    try:
        entry_tempo = globals()[f'entry_http_seg{num_canal}']
        texto_original = entry_tempo.get().strip()
        if not texto_original or "Falta" in texto_original: return

        segundos_finais = converter_string_tempo_para_segundos(texto_original)
        if segundos_finais >= 0:
            if num_canal == 1:
                trig_http_seg_1 = segundos_finais
            elif num_canal == 2:
                trig_http_seg_2 = segundos_finais
            elif num_canal == 3:
                trig_http_seg_3 = segundos_finais
            print(f"[Régie Automação] Canal H{num_canal} fixado em memória: {segundos_finais}s")

            # Mostra temporariamente os segundos puros na caixa antes do Play
            entry_tempo.delete(0, "end")
            entry_tempo.insert(0, str(segundos_finais))

            # Força o refrescamento imediato da telemetria
            if 'atualizar_gatilhos_http_via_painel' in globals():
                atualizar_gatilhos_http_via_painel()
    except Exception as e:
        print(f"[Erro OK] Canal H{num_canal}: {e}")


def procurar_e_importar_som_para_gatilho(num_gatilho):
    """Abre o explorador e guarda o áudio com o nome correto para o gatilho escolhido."""
    caminho = filedialog.askopenfilename(
        title=f"Selecionar Áudio para Alarme T{num_gatilho} (.MP3 ou .WAV)",
        filetypes=[("Ficheiros de Áudio", "*.mp3;*.wav")]
    )
    if caminho:
        try:
            import shutil
            for ext in [f"alarme{num_gatilho}.mp3", f"alarme{num_gatilho}.wav"]:
                caminho_existente = os.path.join(PASTA_DADOS_UTILIZADOR, ext)
                if os.path.exists(caminho_existente):
                    try:
                        os.remove(caminho_existente)
                    except Exception:
                        pass

            extensao = os.path.splitext(caminho)[1].lower()
            shutil.copy(caminho, os.path.join(PASTA_DADOS_UTILIZADOR, f"alarme{num_gatilho}{extensao}"))

            if num_gatilho == 1 and 'seletor_som_t1' in globals():
                seletor_som_t1.set("Custom (Áudio)")
            elif num_gatilho == 2 and 'seletor_som_t2' in globals():
                seletor_som_t2.set("Custom (Áudio)")
            elif num_gatilho == 3 and 'seletor_som_t3' in globals():
                seletor_som_t3.set("Custom (Áudio)")

            if 'atualizar_gatilhos_som_via_painel' in globals():
                atualizar_gatilhos_som_via_painel()
            messagebox.showinfo("Sucesso", f"Áudio para Alarme T{num_gatilho} configurado!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao copiar áudio: {e}")


def atualizar_gatilhos_som_via_painel():
    """Lê as caixas de áudio T1, T2, T3 do ecrã, extrai os segundos com o conversor e atualiza a memória."""
    global gatilho_som_1, gatilho_som_2, gatilho_som_3
    global som_selecionado_1, som_selecionado_2, som_selecionado_3

    def extrair_tempo_som_seguro(entry_obj, valor_atual):
        if not entry_obj: return valor_atual
        texto = entry_obj.get().strip()
        # Se a caixa já tiver o texto de telemetria "Falta", NÃO esmagamos o valor real da memória!
        if "Falta" in texto:
            return valor_atual
        res = converter_string_tempo_para_segundos(texto)
        return res if res >= 0 else valor_atual

    try:
        if 'entry_trig_som1' in globals() and entry_trig_som1:
            gatilho_som_1 = extrair_tempo_som_seguro(entry_trig_som1, gatilho_som_1)
        if 'seletor_som_t1' in globals() and seletor_som_t1:
            som_selecionado_1 = seletor_som_t1.get()

        if 'entry_trig_som2' in globals() and entry_trig_som2:
            gatilho_som_2 = extrair_tempo_som_seguro(entry_trig_som2, gatilho_som_2)
        if 'seletor_som_t2' in globals() and seletor_som_t2:
            som_selecionado_2 = seletor_som_t2.get()

        if 'entry_trig_som3' in globals() and entry_trig_som3:
            gatilho_som_3 = extrair_tempo_som_seguro(entry_trig_som3, gatilho_som_3)
        if 'seletor_som_t3' in globals() and seletor_som_t3:
            som_selecionado_3 = seletor_som_t3.get()

        print(f"[Régie Som] Caches sincronizadas -> T1: {gatilho_som_1}s | T2: {gatilho_som_2}s | T3: {gatilho_som_3}s")
    except Exception:
        pass


def mudar_fonte_interface(event):
    """Altera as fontes adaptativas de toda a interface do utilizador."""
    global fonte_atual, entry_horas, entry_minutos, entry_segundos, lbl_tempo
    try:
        if 'seletor_fontes' in globals() and seletor_fontes is not None:
            fonte_atual = seletor_fontes.get()
        f_g = calcular_fonte(24)
        if 'entry_horas' in globals() and entry_horas is not None:
            entry_horas.config(font=(fonte_atual, f_g, "bold"))
        if 'entry_minutos' in globals() and entry_minutos is not None:
            entry_minutos.config(font=(fonte_atual, f_g, "bold"))
        if 'entry_segundos' in globals() and entry_segundos is not None:
            entry_segundos.config(font=(fonte_atual, f_g, "bold"))
        if 'lbl_tempo' in globals() and lbl_tempo is not None:
            lbl_tempo.config(font=(fonte_atual, calcular_fonte(45), "bold"))
    except Exception:
        pass


def testar_automacao_h1():
    try:
        atualizar_gatilhos_http_via_painel()
        if trig_http_url_1:
            threading.Thread(target=executar_pedido_externo_assincrono,
                             args=(trig_http_url_1, trig_http_met_1, {}, None), daemon=True).start()
    except Exception:
        pass


def testar_automacao_h2():
    try:
        atualizar_gatilhos_http_via_painel()
        if trig_http_url_2:
            threading.Thread(target=executar_pedido_externo_assincrono,
                             args=(trig_http_url_2, trig_http_met_2, {}, None), daemon=True).start()
    except Exception:
        pass


def testar_automacao_h3():
    try:
        atualizar_gatilhos_http_via_painel()
        if trig_http_url_3:
            threading.Thread(target=executar_pedido_externo_assincrono,
                             args=(trig_http_url_3, trig_http_met_3, {}, None), daemon=True).start()
    except Exception:
        pass
# =========================================================================
# INTEGRAÇÃO DE REDE EXTERNA (TUNEL CLOUDFLARE) E ENCERRAMENTO SEGURO
# =========================================================================

def forcar_reset_timer_via_botao():
    """Para o relógio e força a reposição profunda idêntica ao comando do Companion,
    repondo o último tempo configurado pelo operador (tempo_inicial_memoria)."""
    global tempo_restante, tempo_inicial_memoria, lbl_status_tk, lbl_preview_regie_tk

    # Executa a limpeza oficial do motor nativo
    if 'reset_timer_local' in globals():
        if 'root' in globals() and root:
            root.after(0, reset_timer_local)

            # Garante que o teu visor de preview atualiza o texto no ecrã imediatamente
            txt_formatado = formatar_tempo_completo(tempo_restante)
            if 'lbl_preview_regie_tk' in globals() and lbl_preview_regie_tk:
                lbl_preview_regie_tk.set(f"Tempo: {txt_formatado}")

            print(f"[Régie Botão] RESET fixado à força para {txt_formatado}.")


def fechar_aplicacao_seguro():
    """Liquida de forma violenta e limpa todos os processos e threads fantasmas na RAM."""
    try:
        parar_audio_nativo_sistema()
        if 'janela_secundaria' in globals() and janela_secundaria and janela_secundaria.winfo_exists():
            janela_secundaria.destroy()
        root.destroy()
    except Exception:
        pass
    finally:
        # 💥 A TRANCA DE SEGURANÇA: Força o sistema operativo a matar o processo atual e todas as threads Flask!
        import os
        os._exit(0)

# =========================================================================
# MONTAGEM DA INTERFACE VISUAL (TKINTER) - CANTOS ARREDONDADOS COM BORDA
# =========================================================================

janela_principal = Toplevel(root)
janela_principal.title("Cue Timer")
janela_principal.geometry(f"{LARGURA_JANELA}x{ALTURA_JANELA}+{pos_x}+{pos_y}")

# --- AJUSTE DE MOLDURA SEGUNDO O SISTEMA OPERATIVO ---
if SISTEMA_MAC:
    # 🍎 MAC NATIVO: Deixa o Mac desenhar a sua própria janela padrão
    pass
else:
    # 💻 WINDOWS DRACULA FRAMELESS: Força a remoção total da barra branca do Windows
    janela_principal.overrideredirect(True)
    # Define a cor mágica que o Windows vai recortar para criar os cantos redondos
    janela_principal.wm_attributes("-transparentcolor", "#080b12")

# Define a cor de fundo padrão base
janela_principal.configure(bg="#0b0f1a" if SISTEMA_MAC else "#080b12")

try:
    caminho_icone = os.path.join(caminho_base, "app.ico")
    if not SISTEMA_MAC:
        janela_principal.iconbitmap(os.path.join(caminho_base, "app.ico"))

except Exception:
    pass

# Canvas injetado em modo absolute para desenhar a moldura Drácula com cantos redondos
canvas = Canvas(janela_principal, bg="#0b0f1a" if SISTEMA_MAC else "#080b12", highlightthickness=0)
canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)

def criar_retangulo_arredondado(canvas_obj, x1, y1, x2, y2, raio, **kwargs):
    p = [x1+raio, y1, x1+raio, y1, x2-raio, y1, x2-raio, y1, x2, y1, x2, y1+raio, x2, y1+raio, x2, y2-raio, x2, y2-raio, x2, y2-raio, x2, y2, x2-raio, y2, x2-raio, y2, x1+raio, y2, x1+raio, y2, x1, y2, x1, y2-raio, x1, y2-raio, x1, y1+raio, x1, y1+raio, x1, y1]
    return canvas_obj.create_polygon(p, **kwargs, smooth=True)


class BotaoMetal(Canvas):
    """Botão desenhado à mão em Canvas: cantos arredondados + gradiente metálico
    vertical (verde-cyan) + brilho quando ativo. Existe porque o tk.Button normal
    só pinta cor sólida lisa -- sem gradiente, sem cantos redondos, sem brilho.
    Reutiliza criar_retangulo_arredondado() para o contorno; a máscara dos 4
    cantos é feita com arcos pintados na cor de fundo do painel-pai, porque o
    Canvas não tem clip-path nativo."""

    GRAD_ATIVO = ("#1f9d89", "#0d4a41")
    GRAD_INATIVO = ("#142622", "#0a1614")
    COR_BORDA = "#162622"
    COR_BRILHO = "#7ffbe8"
    COR_TEXTO_ATIVO = "#04120f"
    COR_TEXTO_INATIVO = "#e3f7f2"

    def __init__(self, parent, text, command=None, ativo=True, raio=12,
                 fonte=("Arial", 11, "bold"), bg_pai=None, **kwargs):
        bg_pai = bg_pai or parent["bg"]
        super().__init__(parent, highlightthickness=0, bg=bg_pai, cursor="hand2", **kwargs)
        self.command = command
        self.texto = text
        self.ativo = ativo
        self.fonte = fonte
        self.raio = raio
        self.bg_pai = bg_pai
        self._pressionado = False
        self._em_hover = False
        self.bind("<Configure>", lambda e: self._desenhar())
        self.bind("<Button-1>", self._ao_premir)
        self.bind("<ButtonRelease-1>", self._ao_soltar)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _interpolar(self, cor_a, cor_b, t):
        ra, ga, ba = self.winfo_rgb(cor_a)
        rb, gb, bb = self.winfo_rgb(cor_b)
        r = int(ra + (rb - ra) * t) >> 8
        g = int(ga + (gb - ga) * t) >> 8
        b = int(ba + (bb - ba) * t) >> 8
        return f"#{r:02x}{g:02x}{b:02x}"

    def _desenhar(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 6 or h < 6:
            return
        topo, base = self.GRAD_ATIVO if self.ativo else self.GRAD_INATIVO
        if self._em_hover:
            topo = self._interpolar(topo, "#ffffff", 0.12)
        for i in range(h):
            t = i / max(h - 1, 1)
            self.create_line(0, i, w, i, fill=self._interpolar(topo, base, t))

        r = min(self.raio, w / 2, h / 2)
        # máscara arredondada: pinta os 4 cantos com a cor do painel-pai por cima do gradiente
        self.create_arc(-1, -1, 2*r+1, 2*r+1, start=90, extent=90, fill=self.bg_pai, outline=self.bg_pai)
        self.create_arc(w-2*r-1, -1, w+1, 2*r+1, start=0, extent=90, fill=self.bg_pai, outline=self.bg_pai)
        self.create_arc(-1, h-2*r-1, 2*r+1, h+1, start=180, extent=90, fill=self.bg_pai, outline=self.bg_pai)
        self.create_arc(w-2*r-1, h-2*r-1, w+1, h+1, start=270, extent=90, fill=self.bg_pai, outline=self.bg_pai)

        cor_contorno = self.COR_BRILHO if self.ativo else self.COR_BORDA
        criar_retangulo_arredondado(self, 1, 1, w-1, h-1, raio=r, fill="",
                                    outline=cor_contorno, width=2 if self.ativo else 1)

        cor_texto = self.COR_TEXTO_ATIVO if self.ativo else self.COR_TEXTO_INATIVO
        self.create_text(w/2, h/2, text=self.texto, fill=cor_texto, font=self.fonte, justify="center")

    def _hover(self, dentro):
        self._em_hover = dentro
        self._desenhar()

    def _ao_premir(self, event):
        self._pressionado = True

    def _ao_soltar(self, event):
        premido_dentro = self._pressionado
        self._pressionado = False
        if premido_dentro and self.command:
            self.command()

    def set_estado(self, ativo=None, texto=None):
        if ativo is not None:
            self.ativo = ativo
        if texto is not None:
            self.texto = texto
        self._desenhar()


def redimensionar_fundo(event):
    canvas.delete("fundo_moldura")
    if SISTEMA_MAC:
        # 🍎 No Mac, removemos as margens (0) e trincas fixas para o layout expandir sem cortar
        criar_retangulo_arredondado(
            canvas, 0, 0, event.width, event.height,
            raio=20, fill="#0b0f1a", outline="#0b0f1a", width=0, tags="fundo_moldura"
        )
    else:
        # 💻 REPOSIÇÃO WINDOWS: Devolve os cantos arredondados (raio 25) e a borda física outline (#2a3548)
        criar_retangulo_arredondado(
            canvas, 10, 10, event.width-10, event.height-10,
            raio=25, fill="#0b0f1a", outline="#2a3548", width=4, tags="fundo_moldura"
        )
        # Força o canvas de fundo a ficar abaixo dos botões para evitar duplicações fantasmas
        canvas.tag_lower("fundo_moldura")

canvas.bind("<Configure>", redimensionar_fundo)


# Contentor que flutua elastecidamente respeitando os cantos e margens do estúdio
container = Frame(janela_principal, bg="#0b0f1a")
if SISTEMA_MAC:
    # 🍎 NO MAC: Aumentamos o recuo nas laterais para espremer o conteúdo e nada fugir!
    container.place(x=55, y=35, relwidth=1.0, relheight=1.0, width=-110, height=-70)
else:
    # 💻 WINDOWS: Mantém o recuo elástico original para que o conteúdo assente dentro da moldura com borda
    container.place(x=65, y=45, relwidth=1.0, relheight=1.0, width=-130, height=-90)



# Barra de Arraste Superior Customizada (Drag Bar)
frame_drag = Frame(container, bg="#080b12", height=36)
frame_drag.pack(fill='x', pady=(0, 5))
frame_drag.pack_propagate(False)

frame_marca = Frame(frame_drag, bg="#080b12")
frame_marca.pack(side="left", padx=10)
lbl_texto_marca = Label(frame_marca, text="Cue Timer", font=("Arial", 9, "bold"), bg="#080b12", fg="#7d97a3")
lbl_texto_marca.pack(side="left")
# =========================================================================
# BOTÕES DA BARRA SUPERIOR - ADAPTADOS PARA MOLDURA WINDOWS / MAC NATIVA
# =========================================================================
global btn_fullscreen

# Inicializa a flag protetora no escopo global
if 'flag_bloqueio_fullscreen' not in globals():
    flag_bloqueio_fullscreen = False


def alternar_tamanho_janela_local():
    """Alterna entre Fullscreen e Janela Móvel, trancando os automatismos do Windows."""
    global LARGURA_ECRA, ALTURA_ECRA, pos_x, pos_y, flag_bloqueio_fullscreen
    try:
        # Se estiver em modo sem bordas (Fullscreen Dracula ativo), liberta para janela móvel
        if janela_principal.overrideredirect():
            # 💥 TRINCO ATIVO: Avisa o script para NÃO forçar o Fullscreen de volta!
            flag_bloqueio_fullscreen = True

            janela_principal.withdraw()
            janela_principal.overrideredirect(False)
            janela_principal.state('normal')
            janela_principal.geometry(f"1240x700+{pos_x}+{pos_y}")
            janela_principal.deiconify()
            janela_principal.update()

            if 'btn_fullscreen' in globals() and btn_fullscreen:
                btn_fullscreen.config(text="🗖")
            print("[Régie UI] Janela libertada para modo flutuante móvel 1240x700.")

        else:
            # Caso contrário, força o Fullscreen Dracula arrancando a barra
            janela_principal.withdraw()
            janela_principal.overrideredirect(True)
            janela_principal.wm_attributes("-transparentcolor", "#080b12")
            janela_principal.geometry(f"{LARGURA_ECRA}x{ALTURA_ECRA}+0+0")
            janela_principal.state('zoomed')
            janela_principal.deiconify()
            janela_principal.update_idletasks()
            janela_principal.update()

            # 💥 LIBERTA O TRINCO: Permite que o restauro automático volte a funcionar ao subir da barra
            flag_bloqueio_fullscreen = False

            if 'btn_fullscreen' in globals() and btn_fullscreen:
                btn_fullscreen.config(text="🗗")
            print("[Régie UI] Janela trancada em Fullscreen Dracula.")

    except Exception as e:
        print(f"[Erro Alternar Tamanho] {e}")


if not SISTEMA_MAC:
    # 🔴 1. BOTÃO FECHAR (✕)
    btn_fechar = Button(
        frame_drag,
        text="✕",
        font=("Arial", calcular_fonte(12), "bold"),
        bg="#080b12",
        fg="#ef4444",
        bd=0,
        cursor="hand2",
        command=fechar_aplicacao_seguro
    )
    btn_fechar.pack(side="right", padx=(5, 10))

    # 🟡 2. BOTÃO MAXIMIZAR / RESTAURAR (🗖)
    btn_fullscreen = Button(
        frame_drag,
        text="🗗",
        font=("Arial", calcular_fonte(11), "bold"),
        bg="#080b12",
        fg="#34d399",
        bd=0,
        cursor="hand2",
        command=alternar_tamanho_janela_local
    )
    btn_fullscreen.pack(side="right", padx=5)


    # 🟢 3. ÚNICO BOTÃO MINIMIZAR SEGURO (🗕)
    def minimizar_painel_seguro():
        """Desliga a moldura e força o estado normal antes de minimizar para limpar a cache do Windows."""
        try:
            # 1. Liberta as amarras para o Windows aceitar a ordem
            janela_principal.overrideredirect(False)
            janela_principal.update_idletasks()

            # 2. 💥 CORREÇÃO BROADCAST: Mudado de 'iconified' para 'iconic' (Mata o TclError!)
            janela_principal.state('iconic')
        except Exception as e:
            print(f"[Erro Minimizar] {e}")


    btn_minimizar = Button(
        frame_drag,
        text="🗕",
        font=("Arial", calcular_fonte(11), "bold"),
        bg="#080b12",
        fg="#fde68a",
        bd=0,
        cursor="hand2",
        command=minimizar_painel_seguro
    )
    btn_minimizar.pack(side="right", padx=5)


    def forcar_fullscreen_pos_restauro(event=None):
        """Destrói a barra branca do Windows, mas APENAS se o operador não tiver ativado o modo flutuante."""
        global flag_bloqueio_fullscreen
        try:
            # 💥 A BARREIRA: Se o operador carregou no ESC ou no botão, o automático fica proibido de agir!
            if 'flag_bloqueio_fullscreen' in globals() and flag_bloqueio_fullscreen:
                return

            if janela_principal.state() in ['normal', 'zoomed']:
                janela_principal.overrideredirect(True)
                janela_principal.state('zoomed')
                janela_principal.wm_attributes("-transparentcolor", "#080b12")
                if 'btn_fullscreen' in globals() and btn_fullscreen:
                    btn_fullscreen.config(text="🗗")
                janela_principal.update()
        except Exception:
            pass


    # Unimos o gatilho ao foco da janela e à visibilidade. É impossível o Windows falhar ambos!
    janela_principal.bind("<FocusIn>", forcar_fullscreen_pos_restauro)
    janela_principal.bind("<Visibility>", forcar_fullscreen_pos_restauro)

else:
    btn_fullscreen = None
    Label(frame_drag, text=" ", bg="#080b12", width=6).pack(side="left")

lbl_grip = Label(frame_drag, text="═══ ═══", font=("Arial", 10, "bold"), bg="#080b12", fg="#1f2937")
lbl_grip.pack(side="right", padx=10, expand=True)

def iniciar_arrasto(event):
    janela_principal.x_inicial = event.x_root
    janela_principal.y_inicial = event.y_root
    janela_principal.janela_x = janela_principal.winfo_x()
    janela_principal.janela_y = janela_principal.winfo_y()

def mover_janela(event):
    distancia_x = event.x_root - janela_principal.x_inicial
    distancia_y = event.y_root - janela_principal.y_inicial
    janela_principal.geometry(f"+{janela_principal.janela_x + distancia_x}+{janela_principal.janela_y + distancia_y}")

canvas.bind("<Button-1>", iniciar_arrasto)
canvas.bind("<B1-Motion>", mover_janela)
frame_drag.bind("<Button-1>", iniciar_arrasto)
frame_drag.bind("<B1-Motion>", mover_janela)
lbl_grip.bind("<Button-1>", iniciar_arrasto)
lbl_grip.bind("<B1-Motion>", mover_janela)
lbl_texto_marca.bind("<Button-1>", iniciar_arrasto)
lbl_texto_marca.bind("<B1-Motion>", mover_janela)

# Barra de Status do Log de Rede do Flask
frame_ips_topo = Frame(container, bg="#080b12", height=30)
frame_ips_topo.pack(fill="x", pady=(0, 10))
frame_ips_topo.pack_propagate(False)

lbl_ips_rede = Label(frame_ips_topo, text="A aguardar arranque do servidor web...", font=("Arial", 10, "bold"), bg="#080b12", fg="#7d97a3")
lbl_ips_rede.pack(expand=True)

# Contentor Principal que divide o corpo nas duas colunas adaptativas
frame_corpo_colunas = Frame(container, bg="#0b0f1a")
frame_corpo_colunas.pack(fill="both", expand=True, padx=10)

coluna_esquerda = Frame(frame_corpo_colunas, bg="#0b0f1a")
coluna_esquerda.pack(side="left", fill="both", expand=True, padx=(0, 15))
# =========================================================================
# LINHA ÚNICA HORIZONTAL GIGANTE: CONFIGURAÇÕES E DEFINIÇÃO DE TEMPO
# =========================================================================
frame_linha_tempo_total = Frame(coluna_esquerda, bg="#0b0f1a")
frame_linha_tempo_total.pack(fill="x", anchor="w", pady=(calcular_pading(5), calcular_pading(15)))
# =========================================================================
# A. Bloco do Seletor de Fontes e Controlos de Tamanho Local (COMPATÍVEL WIN/MAC)
# =========================================================================
frame_fonte_seletor = Frame(frame_linha_tempo_total, bg="#0b0f1a")
frame_fonte_seletor.pack(side="left", padx=(0, 5))

# 1. Menu Dropdown da Família da Fonte
Label(frame_fonte_seletor, text="FONTE:", font=("Arial", calcular_fonte(9), "bold"), bg="#0b0f1a", fg="#dfe9ec").pack(side="left")
seletor_fontes = Combobox(frame_fonte_seletor, values=["Arial", "Impact", "Segoe UI", "Courier New", "Verdana", "Comic Sans MS", "Times New Roman"], state="readonly", font=("Arial", calcular_fonte(9), "bold"), width=6 if SISTEMA_MAC else 8)
seletor_fontes.set("Arial")
seletor_fontes.pack(side="left", padx=3)
seletor_fontes.bind("<<ComboboxSelected>>", mudar_fonte_interface)

Label(frame_fonte_seletor, text=" ", bg="#0b0f1a", width=1).pack(side="left")

# 2. Botões de Ajuste de Tamanho ( + / - )
# No Mac, encolhemos o texto para caber milimetricamente no layout expandido
tamanho_botoes_txt = 8 if SISTEMA_MAC else 10
largura_botoes_letra = 24 if SISTEMA_MAC else 3

btn_diminuir_letra = Button(frame_fonte_seletor, text="A-", font=("Arial", tamanho_botoes_txt, "bold"), bg="#1f2937", fg="#ef4444", bd=0, width=largura_botoes_letra, command=lambda: alterar_tamanho_fonte_local("minus"))
btn_diminuir_letra.pack(side="left", padx=1)

btn_aumentar_letra = Button(frame_fonte_seletor, text="A+", font=("Arial", tamanho_botoes_txt, "bold"), bg="#1f2937", fg="#34d399", bd=0, width=largura_botoes_letra, command=lambda: alterar_tamanho_fonte_local("plus"))
btn_aumentar_letra.pack(side="left", padx=1)

# 3. Indicador de Leitura de Tamanho Atual (Ex: 150pt)
global lbl_val_tamanho_ui
if not 'tamanho_fonte_timer_atual' in globals():
    tamanho_fonte_timer_atual = 150

lbl_val_tamanho_ui = Label(frame_fonte_seletor, text=f"{tamanho_fonte_timer_atual}pt", font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", width=5)
lbl_val_tamanho_ui.pack(side="left", padx=4)


Label(frame_linha_tempo_total, text="|", font=("Arial", calcular_fonte(12)), bg="#0b0f1a", fg="#1f2937").pack(side="left", padx=4)
# =========================================================================
# PARTE 3: LINHA DE TEMPO, PRESETS DE TEMPO E PAINEL DE MENSAGENS Triplo
# =========================================================================

# B. Grelha Elástica Unificada: Campos colocados LADO A LADO com os seus respetivos botões (+ / -)
frame_hms_alinhado = Frame(frame_linha_tempo_total, bg="#0b0f1a")
frame_hms_alinhado.pack(side="left", padx=3)

# --- Grupo HORAS ---
entry_horas = Entry(frame_hms_alinhado, width=3, font=("Arial", calcular_fonte(24), "bold"), bg="#141b28", fg="#3fd6ea",
                    bd=0, justify="center", insertbackground="#dfe9ec")
entry_horas.insert(0, "01")
entry_horas.pack(side="left", padx=2, ipady=calcular_pading(5))
entry_horas.bind("<KeyRelease>", lambda e: atualizar_tempo_por_inputs())

Button(frame_hms_alinhado, text="+1H", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_horas(1), width=3, bd=0).pack(side="left", padx=1, ipady=calcular_pading(3))
Button(frame_hms_alinhado, text="-1H", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_horas(-1), width=3, bd=0).pack(side="left", padx=(1, 5), ipady=calcular_pading(3))

Label(frame_hms_alinhado, text=":", font=("Arial", calcular_fonte(18), "bold"), bg="#0b0f1a", fg="#dfe9ec").pack(
    side="left", padx=2)

# --- Grupo MINUTOS ---
entry_minutos = Entry(frame_hms_alinhado, width=3, font=("Arial", calcular_fonte(24), "bold"), bg="#141b28",
                      fg="#3fd6ea", bd=0, justify="center", insertbackground="#dfe9ec")
entry_minutos.insert(0, "00")
entry_minutos.pack(side="left", padx=2, ipady=calcular_pading(5))
entry_minutos.bind("<KeyRelease>", lambda e: atualizar_tempo_por_inputs())

Button(frame_hms_alinhado, text="+1M", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_minutos(1), width=3, bd=0).pack(side="left", padx=1, ipady=calcular_pading(3))
Button(frame_hms_alinhado, text="-1M", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_minutos(-1), width=3, bd=0).pack(side="left", padx=(1, 5), ipady=calcular_pading(3))

Label(frame_hms_alinhado, text=":", font=("Arial", calcular_fonte(18), "bold"), bg="#0b0f1a", fg="#dfe9ec").pack(
    side="left", padx=2)

# --- Grupo SEGUNDOS ---
entry_segundos = Entry(frame_hms_alinhado, width=3, font=("Arial", calcular_fonte(24), "bold"), bg="#141b28",
                       fg="#3fd6ea", bd=0, justify="center", insertbackground="#dfe9ec")
entry_segundos.insert(0, "00")
entry_segundos.pack(side="left", padx=2, ipady=calcular_pading(5))
entry_segundos.bind("<KeyRelease>", lambda e: atualizar_tempo_por_inputs())

Button(frame_hms_alinhado, text="+5S", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_segundos(5), width=3, bd=0).pack(side="left", padx=1, ipady=calcular_pading(3))
Button(frame_hms_alinhado, text="-5S", font=("Arial", calcular_fonte(12), "bold"), bg="#1f2937", fg="#dfe9ec",
       command=lambda: alterar_segundos(-5), width=3, bd=0).pack(side="left", padx=1, ipady=calcular_pading(3))

Label(frame_linha_tempo_total, text="|", font=("Arial", calcular_fonte(12)), bg="#0b0f1a", fg="#1f2937").pack(
    side="left", padx=4)

# C. Inputs de Minutos de Alerta Customizados no Fim da Mesma Linha
frame_alertas_linha = Frame(frame_linha_tempo_total, bg="#0b0f1a")
frame_alertas_linha.pack(side="left", padx=(3, 0))

Label(frame_alertas_linha, text="⚠️ AMAR:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#eab308").grid(
    row=0, column=0, padx=1)
entry_alerta_amarelo = Entry(frame_alertas_linha, width=3, font=("Arial", calcular_fonte(15), "bold"), bg="#141b28",
                             fg="#eab308", bd=0, justify="center", insertbackground="#dfe9ec")
entry_alerta_amarelo.insert(0, "3")
entry_alerta_amarelo.grid(row=0, column=1, padx=2, ipady=calcular_pading(3))

Label(frame_alertas_linha, text="🚨 VERM:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#ef4444").grid(
    row=0, column=2, padx=(5, 1))
entry_alerta_vermelho = Entry(frame_alertas_linha, width=3, font=("Arial", calcular_fonte(15), "bold"), bg="#141b28",
                              fg="#ef4444", bd=0, justify="center", insertbackground="#dfe9ec")
entry_alerta_vermelho.insert(0, "1")
entry_alerta_vermelho.grid(row=0, column=3, padx=2, ipady=calcular_pading(3))

# Contentor do Andar do Meio das Duas Colunas Adaptativas
frame_corpo_medio = Frame(container, bg="#0b0f1a")
frame_corpo_medio.pack(fill="both", expand=True, padx=15, pady=5)

sub_col_esquerda = Frame(frame_corpo_medio, bg="#0b0f1a")
sub_col_esquerda.pack(side="left", fill="both", expand=True, padx=(0, 10))

# =========================================================================
# GRELHA ELÁSTICA DE PRESETS RÁPIDOS DE TEMPO (ADAPTATIVA)
# =========================================================================
lbl_presets = Label(sub_col_esquerda, text="PRESETS RÁPIDOS DE TEMPO:", font=("Arial", calcular_fonte(9), "bold"),
                    bg="#0b0f1a", fg="#dfe9ec")
lbl_presets.pack(anchor="w", pady=(2, 2))

frame_grid_presets = Frame(sub_col_esquerda, bg="#0b0f1a")
frame_grid_presets.pack(fill="both", expand=True, anchor="w")

for c in range(5):
    frame_grid_presets.columnconfigure(c, weight=1)

etiquetas_iniciais = ["30s", "1m", "2m", "3m", "5m", "10m", "15m", "20m", "30m", "60m"]


# 💥 BOTAO ISOLADO: Cola isto dentro da tua barra de comandos antiga
btn_reset_avktimer = Button(
    frame_comandos_principais if 'frame_comandos_principais' in globals() else container,
    text="🔄 RESET",
    font=("Arial", calcular_fonte(12), "bold") if 'calcular_fonte' in globals() else ("Arial", 12, "bold"),
    bg="#b45309",
    fg="#000000",
    bd=0,
    command=forcar_reset_timer_via_botao
)
# Lembra-te de o posicionar usando o teu método antigo (seja .pack(side="left") ou .grid(row=0, column=X))
btn_reset_avktimer.pack(side="left", padx=4, ipady=10) # 👈 Ajusta o .pack ou .grid conforme os teus outros botões!



def capturar_para_preset(idx):
    """Guarda o tempo digitado atualmente nas caixas para dentro do preset selecionado."""
    try:
        h = int(entry_horas.get()) if entry_horas.get() else 0
        m = int(entry_minutos.get()) if entry_minutos.get() else 0
        s = int(entry_segundos.get()) if entry_segundos.get() else 0
        segundos_totais = (h * 3600) + (m * 60) + s

        valores_presets[idx] = segundos_totais
        texto_formatado = formatar_tempo_completo(segundos_totais)
        botoes_presets_referencias[idx].config(text=texto_formatado)
    except Exception:
        pass


# Desenha as duas linhas de botões (SET superior e Disparo de tempo inferior)
for i in range(10):
    l, c = (i // 5) * 2, i % 5
    Button(frame_grid_presets, text="SET", font=("Arial", calcular_fonte(7), "bold"), bg="#374151", fg="#dfe9ec", bd=0,
           command=lambda idx=i: capturar_para_preset(idx)).grid(row=l, column=c, padx=3, pady=(1, 1), ipady=1,
                                                                 sticky="ew")
    bp = Button(frame_grid_presets, text=etiquetas_iniciais[i], font=("Arial", calcular_fonte(10), "bold"),
                bg="#1a2333", fg="#3fd6ea", bd=0, command=lambda idx=i: aplicar_preset_index(idx))
    bp.grid(row=l + 1, column=c, padx=3, pady=(1, 4), ipady=calcular_pading(8), sticky="ew")
    botoes_presets_referencias.append(bp)
# =========================================================================
# ⏱️ NOVO VISOR DE PREVIEW DO RELÓGIO (MONITORIZAÇÃO DA RÉGIE ISOLADA)
# =========================================================================
Label(sub_col_esquerda, text="―" * 35, font=("Arial", calcular_fonte(8)), bg="#0b0f1a", fg="#1f2937").pack(fill="x", pady=(5, 2))

lbl_tit_preview = Label(sub_col_esquerda, text="⏱️ MONITOR DE CONTAGEM REGRESSIVA:", font=("Arial", calcular_fonte(9), "bold"), bg="#0b0f1a", fg="#dfe9ec")
lbl_tit_preview.pack(anchor="w", pady=(2, 4))

frame_visor_preview = Frame(sub_col_esquerda, bg="#080b12", bd=0)
frame_visor_preview.pack(fill="both", expand=True, ipady=15, pady=(2, 5))

# 💥 INJEÇÃO DE VARIÁVEL EXCLUSIVA DA RÉGIE (Acaba com os fantasmas e colisões!)
lbl_preview_regie_tk = StringVar()
lbl_preview_regie_tk.set("Tempo: 00:00:00")

lbl_tempo_preview = Label(
    frame_visor_preview,
    textvariable=lbl_preview_regie_tk,
    font=("Arial", calcular_fonte(32), "bold"),
    bg="#080b12",
    fg="#3fd6ea"
)
lbl_tempo_preview.pack(expand=True, fill="both")


# =========================================================================
# ABRIR SUBCOLUNA DA DIREITA PARA MENSAGENS E GATILHOS
# =========================================================================
sub_col_direita = Frame(frame_corpo_medio, bg="#0b0f1a")
sub_col_direita.pack(side="right", fill="both", expand=True, padx=(10, 0))



# =========================================================================
# PAINEL DE MENSAGENS EM TEMPO REAL (MOTO PROTEGIDO CONTRA FUROS VISUAIS)
# =========================================================================
def atualizar_estilo_botao_msg(botao, texto):
    """Calcula o tamanho do texto e ajusta a fonte dinamicamente para caber no botão."""
    total_caracteres = len(texto)
    if total_caracteres <= 6:
        tamanho_fonte = calcular_fonte(12)
        texto_formatado = texto
    elif total_caracteres <= 11:
        tamanho_fonte = calcular_fonte(10)
        texto_formatado = texto
    elif total_caracteres <= 16:
        tamanho_fonte = calcular_fonte(9)
        texto_formatado = texto
    else:
        tamanho_fonte = calcular_fonte(8)
        metade = total_caracteres // 2
        texto_formatado = texto[:metade] + "\n" + texto[metade:]
    botao.config(text=texto_formatado, font=("Arial", tamanho_fonte, "bold"))


lbl_tit_msg = Label(sub_col_direita, text="MENSAGEM EM TEMPO REAL:", font=("Arial", calcular_fonte(9), "bold"),
                    bg="#0b0f1a", fg="#dfe9ec")
lbl_tit_msg.pack(anchor="w", pady=(2, 2))

frame_msg_row = Frame(sub_col_direita, bg="#0b0f1a")
frame_msg_row.pack(fill="x", anchor="w", pady=1)
frame_msg_row.columnconfigure(0, weight=3)
frame_msg_row.columnconfigure((1, 2), weight=1)

entry_mensagem = Entry(frame_msg_row, font=("Arial", calcular_fonte(11), "bold"), bg="#141b28", fg="#3fd6ea", bd=0,
                       insertbackground="#dfe9ec")
entry_mensagem.grid(row=0, column=0, padx=(0, 4), ipady=calcular_pading(4), sticky="ew")

btn_enviar_msg = Button(frame_msg_row, text="ENVIAR", font=("Arial", calcular_fonte(8), "bold"), bg="#0d9488",
                        fg="white", bd=0, command=enviar_mensagem_ecra)
btn_enviar_msg.grid(row=0, column=1, padx=2, sticky="nsew")

btn_limpar_msg = Button(frame_msg_row, text="LIMPAR", font=("Arial", calcular_fonte(8), "bold"), bg="#b91c1c",
                        fg="white", bd=0, command=limpar_mensagem_ecra)
btn_limpar_msg.grid(row=0, column=2, padx=(2, 0), sticky="nsew")

# =========================================================================
# GRELHA DE PRESETS DE MENSAGENS RÁPIDAS (ADAPTATIVA 5 COLUNAS)
# =========================================================================
frame_grelha_msg_presets = Frame(sub_col_direita, bg="#0b0f1a")
frame_grelha_msg_presets.pack(fill="both", expand=True, anchor="w", pady=(5, 0))

# Força a distribuição elástica de 5 colunas iguais para as mensagens
for c in range(5):
    frame_grelha_msg_presets.columnconfigure(c, weight=1)

etiquetas_msg_iniciais = ["PRESET 1", "PRESET 2", "PRESET 3", "PRESET 4", "PRESET 5", "PRESET 6", "PRESET 7",
                          "PRESET 8", "PRESET 9", "PRESET 10"]

# Desenha a matriz: Linha par = CAPTURAR, Linha ímpar = DISPARAR MENSAGEM
for i in range(10):
    l, c = (i // 5) * 2, i % 5

    # Botão superior para CAPTURAR o texto atual da entry_mensagem para o preset
    Button(frame_grelha_msg_presets, text="M-SET", font=("Arial", calcular_fonte(7), "bold"), bg="#374151",
           fg="#dfe9ec", bd=0,
           command=lambda idx=i: capturar_preset_msg(idx)).grid(row=l, column=c, padx=2, pady=(1, 1), ipady=1,
                                                                sticky="ew")

    # Garante que o teu botão bm vai buscar o texto de arranque à tua nova lista:
    bm = Button(frame_grelha_msg_presets, text=textos_presets_msg[i], font=("Arial", calcular_fonte(9), "bold"),
                bg="#1a2333", fg="#3fd6ea", bd=0, command=lambda idx=i: disparar_preset_msg(idx))

    bm.grid(row=l + 1, column=c, padx=2, pady=(1, 4), ipady=calcular_pading(6), sticky="nsew")

    # Guarda a referência para podermos encolher a fonte dinamicamente via atualizar_estilo_botao_msg()
    botoes_msg_referencias.append(bm)
# =========================================================================
# GRELHA CORPORATIVA ELÁSTICA (CORREÇÃO DE COR TRANS-COLOR v1.3)
# =========================================================================
# 💥 MUDANÇA: O frame-mãe assume o bg Dracula para tapar o furo do Windows
frame_matriz_direita = Frame(sub_col_direita, bg="#0b0f1a")
frame_matriz_direita.pack(fill="both", expand=True, padx=5, pady=2)

frame_matriz_direita.columnconfigure((0, 1, 2, 4, 5), weight=0)
frame_matriz_direita.columnconfigure(3, weight=1)

fonte_botoes_pequenos = ("Arial", 9 if SISTEMA_MAC else calcular_fonte(7), "bold")
fonte_botoes_trig = ("Arial", calcular_fonte(8), "bold")
largura_metodo = 4 if SISTEMA_MAC else 5
largura_url_char = 8 if SISTEMA_MAC else 20

## ─────────────────────────────────────────────────────────────────────────
# SECTOR 1: ⏱️ ALARMES INDEPENDENTES DE ÁUDIO (VERSÃO BROADCAST COMPILADA)
# ─────────────────────────────────────────────────────────────────────────
Label(frame_matriz_direita, text="⏱️ ALARMES SONOROS (DIGITE OU COLOQUE MM:SS):", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#7d97a3").grid(row=0, column=0, columnspan=6, sticky="w", pady=(2, 6))

lista_sons_regie = ["Beep", "Alarme 1", "Alarme 2", "Sinal Horário", "Fim de Tempo"]

# --- LINHA T1 ---
Label(frame_matriz_direita, text="T1:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=1, column=0, padx=2, pady=3, sticky="w")
entry_trig_som1 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_trig_som1.grid(row=1, column=1, padx=2, ipady=2, sticky="ew")
entry_trig_som1.bind("<KeyRelease>", lambda e: atualizar_gatilhos_som_via_painel())

seletor_som_t1 = Combobox(frame_matriz_direita, values=lista_sons_regie, state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=10)
seletor_som_t1.set("Beep") # 💥 FIXA O BEEP DE ARRANQUE PARA NÃO FICAR EM BRANCO!
seletor_som_t1.grid(row=1, column=2, padx=2, sticky="ew")
seletor_som_t1.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_som_via_painel())

Button(frame_matriz_direita, text="BUSCAR 1", font=fonte_botoes_pequenos, bg="#0891b2", fg="white", bd=0, command=lambda: procurar_e_importar_som_para_gatilho(1)).grid(row=1, column=3, padx=2, sticky="nsew", ipady=1)
lbl_som_feedback1 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_som_feedback1.grid(row=1, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=lambda: threading.Thread(target=tocar_som_background, args=(1,), daemon=True).start()).grid(row=1, column=5, padx=2, sticky="nsew")

# --- LINHA T2 ---
Label(frame_matriz_direita, text="T2:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=2, column=0, padx=2, pady=3, sticky="w")
entry_trig_som2 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_trig_som2.grid(row=2, column=1, padx=2, ipady=2, sticky="ew")
entry_trig_som2.bind("<KeyRelease>", lambda e: atualizar_gatilhos_som_via_painel())

seletor_som_t2 = Combobox(frame_matriz_direita, values=lista_sons_regie, state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=10)
seletor_som_t2.set("Beep") # 💥 FIXA O BEEP DE ARRANQUE PARA NÃO FICAR EM BRANCO!
seletor_som_t2.grid(row=2, column=2, padx=2, sticky="ew")
seletor_som_t2.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_som_via_painel())

Button(frame_matriz_direita, text="BUSCAR 2", font=fonte_botoes_pequenos, bg="#0891b2", fg="white", bd=0, command=lambda: procurar_e_importar_som_para_gatilho(2)).grid(row=2, column=3, padx=2, sticky="nsew", ipady=1)
lbl_som_feedback2 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_som_feedback2.grid(row=2, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=lambda: threading.Thread(target=tocar_som_background, args=(2,), daemon=True).start()).grid(row=2, column=5, padx=2, sticky="nsew")

# --- LINHA T3 ---
Label(frame_matriz_direita, text="T3:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=3, column=0, padx=2, pady=3, sticky="w")
entry_trig_som3 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_trig_som3.grid(row=3, column=1, padx=2, ipady=2, sticky="ew")
entry_trig_som3.bind("<KeyRelease>", lambda e: atualizar_gatilhos_som_via_painel())

seletor_som_t3 = Combobox(frame_matriz_direita, values=lista_sons_regie, state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=10)
seletor_som_t3.set("Beep") # 💥 FIXA O BEEP DE ARRANQUE PARA NÃO FICAR EM BRANCO!
seletor_som_t3.grid(row=3, column=2, padx=2, sticky="ew")
seletor_som_t3.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_som_via_painel())

Button(frame_matriz_direita, text="BUSCAR 3", font=fonte_botoes_pequenos, bg="#0891b2", fg="white", bd=0, command=lambda: procurar_e_importar_som_para_gatilho(3)).grid(row=3, column=3, padx=2, sticky="nsew", ipady=1)
lbl_som_feedback3 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_som_feedback3.grid(row=3, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=lambda: threading.Thread(target=tocar_som_background, args=(3,), daemon=True).start()).grid(row=3, column=5, padx=2, sticky="nsew")

# Divisória de Estúdio
Label(frame_matriz_direita, text="―" * (35 if SISTEMA_MAC else 65), font=("Arial", calcular_fonte(8)), bg="#0b0f1a", fg="#1f2937").grid(row=4, column=0, columnspan=6, pady=4)

# ─────────────────────────────────────────────────────────────────────────
# SECTOR 2: 🌐 AUTOMACÃO HTTP EXTERNA (bg corrigido para #0b0f1a)
# ─────────────────────────────────────────────────────────────────────────
Label(frame_matriz_direita, text="🌐 AUTOMAÇÃO WEB HTTP EXTERNA:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#7d97a3").grid(row=5, column=0, columnspan=6, sticky="w", pady=(2, 6))

# --- LINHA H1 ---
Label(frame_matriz_direita, text="H1:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=6, column=0, padx=2, pady=3, sticky="w")
entry_http_seg1 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_http_seg1.grid(row=6, column=1, padx=2, ipady=2, sticky="ew")
entry_http_seg1.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

seletor_http_met1 = Combobox(frame_matriz_direita, values=["GET", "POST"], state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=largura_metodo)
seletor_http_met1.set("GET")
seletor_http_met1.grid(row=6, column=2, padx=2, sticky="ew")
seletor_http_met1.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_http_via_painel())

entry_http_url1 = Entry(frame_matriz_direita, font=("Arial", calcular_fonte(9)), bg="#141b28", fg="#ffffff", bd=0, width=largura_url_char)
entry_http_url1.grid(row=6, column=3, padx=2, ipady=2, sticky="ew")
entry_http_url1.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

lbl_http_feedback1 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_http_feedback1.grid(row=6, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=testar_automacao_h1).grid(row=6, column=5, padx=2, sticky="nsew")

# --- LINHA H2 ---
Label(frame_matriz_direita, text="H2:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=7, column=0, padx=2, pady=3, sticky="w")
entry_http_seg2 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_http_seg2.grid(row=7, column=1, padx=2, ipady=2, sticky="ew")
entry_http_seg2.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

seletor_http_met2 = Combobox(frame_matriz_direita, values=["GET", "POST"], state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=largura_metodo)
seletor_http_met2.set("GET")
seletor_http_met2.grid(row=7, column=2, padx=2, sticky="ew")
seletor_http_met2.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_http_via_painel())

entry_http_url2 = Entry(frame_matriz_direita, font=("Arial", calcular_fonte(9)), bg="#141b28", fg="#ffffff", bd=0, width=largura_url_char)
entry_http_url2.grid(row=7, column=3, padx=2, ipady=2, sticky="ew")
entry_http_url2.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

lbl_http_feedback2 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_http_feedback2.grid(row=7, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=testar_automacao_h2).grid(row=7, column=5, padx=2, sticky="nsew")
# --- LINHA H3 (CORRIGIDA COM BG DRACULA OPACO) ---
Label(frame_matriz_direita, text="H3:", font=("Arial", calcular_fonte(8), "bold"), bg="#0b0f1a", fg="#3fd6ea").grid(row=8, column=0, padx=2, pady=3, sticky="w")
entry_http_seg3 = Entry(frame_matriz_direita, width=8, font=("Arial", calcular_fonte(9), "bold"), bg="#141b28", fg="#3fd6ea", bd=0, justify="center")
entry_http_seg3.grid(row=8, column=1, padx=2, ipady=2, sticky="ew")
entry_http_seg3.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

seletor_http_met3 = Combobox(frame_matriz_direita, values=["GET", "POST"], state="readonly", font=("Arial", calcular_fonte(8), "bold"), width=largura_metodo)
seletor_http_met3.set("GET")
seletor_http_met3.grid(row=8, column=2, padx=2, sticky="ew")
seletor_http_met3.bind("<<ComboboxSelected>>", lambda e: atualizar_gatilhos_http_via_painel())

entry_http_url3 = Entry(frame_matriz_direita, font=("Arial", calcular_fonte(9)), bg="#141b28", fg="#ffffff", bd=0, width=largura_url_char)
entry_http_url3.grid(row=8, column=3, padx=2, ipady=2, sticky="ew")
entry_http_url3.bind("<KeyRelease>", lambda e: atualizar_gatilhos_http_via_painel())

lbl_http_feedback3 = Label(frame_matriz_direita, text="---", font=("Arial", calcular_fonte(8), "bold"), bg="#141b28", fg="#7d97a3", width=10)
lbl_http_feedback3.grid(row=8, column=4, padx=2, sticky="nsew")
Button(frame_matriz_direita, text="TEST", font=fonte_botoes_pequenos, bg="#374151", fg="#dfe9ec", bd=0, command=testar_automacao_h3).grid(row=8, column=5, padx=2, sticky="nsew")

# Divisória de Estúdio (Pintada em bg="#0b0f1a")
Label(frame_matriz_direita, text="―" * (35 if SISTEMA_MAC else 65), font=("Arial", calcular_fonte(8)), bg="#0b0f1a", fg="#1f2937").grid(row=9, column=0, columnspan=6, pady=4)

# ─────────────────────────────────────────────────────────────────────────
# SECTOR 3: 🎛️ PAINEL DE INTERRUPTORES (TOGGLES) - BG OPACO PROTEGIDO
# ─────────────────────────────────────────────────────────────────────────
frame_botoes_toggle_linha = Frame(frame_matriz_direita, bg="#0b0f1a")
frame_botoes_toggle_linha.grid(row=10, column=0, columnspan=6, sticky="ew", pady=(2, 2))
frame_botoes_toggle_linha.columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)

btn_modo_zero = Button(frame_botoes_toggle_linha, text="MODO NEGATIVO", bg="#0891b2", fg="white", font=fonte_botoes_trig, bd=0, command=toggle_modo_zero)
btn_modo_zero.grid(row=0, column=0, padx=1, pady=2, sticky="nsew", ipady=2)

btn_alternar_web = Button(frame_botoes_toggle_linha, text="MODO RELÓGIO", bg="#0e7490", fg="#dfe9ec", font=fonte_botoes_trig, bd=0, command=alternar_modo_visualizacao)
btn_alternar_web.grid(row=0, column=1, padx=1, pady=2, sticky="nsew", ipady=2)

altura_botao_toggle = calcular_fonte(26)

btn_ecran_on = BotaoMetal(frame_botoes_toggle_linha, text="ECRÃ: LIGAR", command=generar_janela_nativa_directx,
                          ativo=True, raio=9, fonte=fonte_botoes_trig, height=altura_botao_toggle, bg_pai="#0b0f1a")
btn_ecran_on.grid(row=0, column=2, padx=1, pady=2, sticky="nsew")

btn_ecran_off = BotaoMetal(frame_botoes_toggle_linha, text="ECRÃ: DESLIGAR", command=fechar_ecran_nativo_botao,
                           ativo=True, raio=9, fonte=fonte_botoes_trig, height=altura_botao_toggle, bg_pai="#0b0f1a")
btn_ecran_off.grid(row=0, column=3, padx=1, pady=2, sticky="nsew")

btn_toggle_piscar = BotaoMetal(frame_botoes_toggle_linha, text="💥 PISCAR", command=toggle_permissao_piscar,
                               ativo=permitir_piscar_pos_zero, raio=9, fonte=fonte_botoes_trig,
                               height=altura_botao_toggle, bg_pai="#0b0f1a")
btn_toggle_piscar.grid(row=0, column=4, padx=1, pady=2, sticky="nsew")

btn_mute_som = BotaoMetal(frame_botoes_toggle_linha, text="🔊 SOM: ON", command=toggle_mute_som,
                          ativo=som_ativado, raio=9, fonte=fonte_botoes_trig,
                          height=altura_botao_toggle, bg_pai="#0b0f1a")
btn_mute_som.grid(row=0, column=5, padx=1, pady=2, sticky="nsew")

btn_parar_som_emerg = Button(frame_botoes_toggle_linha, text="🛑 PARAR\n SOM", bg="#7f1d1d", fg="white", font=fonte_botoes_trig, bd=0, command=parar_audio_nativo_sistema)
btn_parar_som_emerg.grid(row=0, column=6, padx=1, pady=2, sticky="nsew", ipady=2)

# 💥 CORREÇÃO BROADCAST: Fundo da linha divisória final cravado em #0b0f1a para extinguir a transparência!
Label(frame_matriz_direita, text="―" * (35 if SISTEMA_MAC else 65), font=("Arial", calcular_fonte(8)), bg="#0b0f1a", fg="#1f2937").grid(row=11, column=0, columnspan=6, pady=4)



# =========================================================================
# 3. CINCO GRANDES BOTÕES DE ACÇÃO CORE DO FUNDO (DESLOCADOS PARA A ESQUERDA)
# =========================================================================
frame_botoes_acao = Frame(container, bg="#0b0f1a")
frame_botoes_acao.pack(fill="x", side="top", expand=True, pady=(10, 5), padx=(0, 25 if SISTEMA_MAC else 0))
frame_botoes_acao.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

pading_botao_core = 8 if SISTEMA_MAC else calcular_pading(8)
altura_botao_core = calcular_fonte(34)
fonte_botao_core = ("Arial", calcular_fonte(11), "bold")

BotaoMetal(frame_botoes_acao, text="INICIAR", command=iniciar_timer,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=0, padx=6, pady=pading_botao_core, sticky="nsew")

BotaoMetal(frame_botoes_acao, text="PAUSAR", command=pausar_timer,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=1, padx=6, pady=pading_botao_core, sticky="nsew")

BotaoMetal(frame_botoes_acao, text="ATUALIZAR", command=executar_override_tempo,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=2, padx=6, pady=pading_botao_core, sticky="nsew")

BotaoMetal(frame_botoes_acao, text="STOP", command=parar_timer,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=3, padx=6, pady=pading_botao_core, sticky="nsew")

BotaoMetal(frame_botoes_acao, text="REINICIAR", command=reiniciar_timer,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=4, padx=6, pady=pading_botao_core, sticky="nsew")

BotaoMetal(frame_botoes_acao, text="📋 CUES", command=abrir_janela_cues,
           height=altura_botao_core, fonte=fonte_botao_core, bg_pai="#0b0f1a"
).grid(row=0, column=5, padx=6, pady=pading_botao_core, sticky="nsew")

# --- SYSTEM TRAY (PROTEÇÃO HÍBRIDA PARA WINDOWS E MAC) ---
try:
    if not SISTEMA_MAC:
        import pystray
        from PIL import Image


        def criar_icone_system_tray():
            if 'icone_tray_criado' in globals() and globals()['icone_tray_criado']:
                return
            try:
                caminho_ico = os.path.join(caminho_base, "app.ico")
                if os.path.exists(caminho_ico):
                    imagem = Image.open(caminho_ico)
                    menu = pystray.Menu(pystray.MenuItem('Fechar Cue Timer', fechar_aplicacao_seguro))
                    icon = pystray.Icon("CueTimer", imagem, "Cue Timer Server", menu)
                    globals()['icone_tray_criado'] = True
                    threading.Thread(target=icon.run, daemon=True).start()
            except Exception:
                pass


        criar_icone_system_tray()
except Exception:
    pass

# --- ACIONAMENTO FINAL EXCLUSIVO DAS THREADS ASSÍNCRONAS (NÃO REPETIR) ---
print("\n[Cue Timer Core] A disparar motores assíncronos de estúdio...")

carregar_lista_cues()

threading.Thread(target=iniciar_servidor_flask, daemon=True).start()
threading.Thread(target=contagem_decrescente, daemon=True).start()
threading.Thread(target=loop_atualizacao_ecran_nativo, daemon=True).start()
threading.Thread(target=loop_deteccao_slides, daemon=True).start()
# 💥 Cloudflare removida de forma limpa aqui para evitar falhas

print("[Cue Timer Core] Motores ativos. A escutar Companion e Browser na porta 4545.\n")
# --- 🍎 CRIAÇÃO DA BARRA DE MENUS NATIVA DO MACOS 🍎 ---
if SISTEMA_MAC:
    from tkinter import Menu

    def alternar_fullscreen_palco_menu():
        """Força o gatilho de fullscreen via Menu no Mac se o ecrã de palco existir."""
        if 'janela_secundaria' in globals() and janela_secundaria and janela_secundaria.winfo_exists():
            estado_atual = janela_secundaria.wm_attributes("-fullscreen")
            janela_secundaria.wm_attributes("-fullscreen", not estado_atual)

    # Inicializa a barra global no Mac
    barra_menus = Menu(janela_principal)

    # Menu 1: Controlos do Ecrã de Palco
    menu_display = Menu(barra_menus, tearoff=0)
    menu_display.add_command(label="💻 Ligar Monitor de Palco", command=generar_janela_nativa_directx)
    menu_display.add_command(label="🗖 Ativar/Desativar Ecrã Inteiro", command=alternar_fullscreen_palco_menu)
    menu_display.add_separator()
    menu_display.add_command(label="🛑 Desligar Monitor de Palco", command=fechar_ecran_nativo_botao)

    # Adiciona a aba à barra de topo
    barra_menus.add_cascade(label="Monitor de Palco", menu=menu_display)

    # Configura o Mac para assumir este menu
    janela_principal.config(menu=barra_menus)

# --- 🖥️ WINDOWS: MOTOR DE ARRANCAR EM FULLSCREEN TOTAL AUTOMÁTICO v1.4 🖥️ ---
# Força a janela a nascer maximizada ocupando 100% do ecrã e espalhando os componentes
if not SISTEMA_MAC:
    # 1. Garante que a janela está visível e com a moldura padrão ativa para o boot
    janela_principal.deiconify()
    janela_principal.overrideredirect(False)

    # 2. Força o Windows a esticar o Tkinter para o tamanho máximo do teu monitor (Maximizado)
    janela_principal.state('zoomed')

    # 3. Processa e assenta todas as grelhas elásticas e visores na resolução máxima
    janela_principal.update_idletasks()
    janela_principal.update()

    # 4. Remove as bordas pretas mantendo o tamanho gigante maximizado e o fundo Dracula opaco
    janela_principal.overrideredirect(True)
    janela_principal.wm_attributes("-transparentcolor", "#080b12")
    janela_principal.update()
    print("[Régie UI] Janela disparada em Fullscreen Maximizado. Elasticidade ativa a 100%.")
else:
    # No Mac, mantém o comportamento fluido nativo estável original
    janela_principal.geometry(f"{LARGURA_JANELA}x{ALTURA_JANELA}+{pos_x}+{pos_y}")
# =========================================================================
# ATALHOS DE TECLADO ABSOLUTOS (MATA A TRANCA DE FOCO DO WINDOWS)
# =========================================================================
# 💥 LIMPEZA: O 'bind' antigo foi removido daqui para extinguir o duplo disparo em milissegundos!
# O bind_all garante que a tecla ESCAPE funciona mesmo com caixas Entry ou botões selecionados.
janela_principal.bind_all("<Escape>", lambda event: alternar_tamanho_janela_local() if 'alternar_tamanho_janela_local' in globals() else None)

# --- SINCRONIZAÇÃO INICIAL E EXECUÇÃO DO LOOP PRINCIPAL ---
def forcar_acendimento_relogio_inicial():
    global tempo_restante, lbl_status_tk, lbl_preview_regie_tk
    try:
        if 'atualizar_tempo_por_inputs' in globals():
            atualizar_tempo_por_inputs()

        if 'tempo_restante' not in globals() or tempo_restante <= 0:
            tempo_restante = 3600

        txt_inicial_ecra = formatar_tempo_completo(tempo_restante)

        # Alimenta as duas frentes em simultâneo (Palco e Preview da Régie)
        if 'lbl_status_tk' in globals() and lbl_status_tk:
            lbl_status_tk.set(f"Tempo: {txt_inicial_ecra}")
        if 'lbl_preview_regie_tk' in globals() and lbl_preview_regie_tk:
            lbl_preview_regie_tk.set(f"Tempo: {txt_inicial_ecra}")

        print(f"[Régie UI] Visores sincronizados em separado: {txt_inicial_ecra}")
    except Exception as e:
        print(f"[Erro Arranque Visor] {e}")


# Agendamos o acendimento do relógio para 100ms após o mainloop abrir, limpando a tranca do Windows
janela_principal.after(100, forcar_acendimento_relogio_inicial)

# Protocolos de fecho seguro e arranque do loop principal
root.protocol("WM_DELETE_WINDOW", fechar_aplicacao_seguro)
janela_principal.protocol("WM_DELETE_WINDOW", fechar_aplicacao_seguro)
root.mainloop()
