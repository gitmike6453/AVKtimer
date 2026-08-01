const { InstanceBase, runEntrypoint, InstanceStatus } = require('@companion-module/base')

class AVKTimerInstance extends InstanceBase {
	// 1. Cria as caixas de texto nas configurações do Companion
	getConfigFields() {
		return [
			{
				type: 'textinput',
				id: 'host',
				label: 'IP do Computador (Timer)',
				width: 8,
				regex: this.REGEX_IP
			},
			{
				type: 'textinput',
				id: 'port',
				label: 'Porta da Aplicação',
				width: 4,
				default: '4545'
			},
			{
				type: 'number',
				id: 'poll_ms',
				label: 'Intervalo de leitura do estado (ms)',
				width: 4,
				default: 500,
				min: 200,
				max: 5000
			}
		]
	}

	// 2. Executado quando adicionas o módulo
	async init(config) {
		this.config = config
		this.updateStatus(InstanceStatus.Ok) // Bolha fica VERDE na hora
		this.initActions()
		this.initVariables()
		this.iniciarPolling()
	}

	async destroy() {
		if (this.intervaloPoll) {
			clearInterval(this.intervaloPoll)
		}
		this.log('debug', 'Módulo AVK terminado.')
	}

	async configUpdated(config) {
		this.config = config
		this.iniciarPolling()
	}

	initVariables() {
		this.setVariableDefinitions([
			{ variableId: 'tempo', name: 'Tempo restante (HH:MM:SS)' },
			{ variableId: 'estado', name: 'Estado (normal/alerta/critico/fim)' },
			{ variableId: 'mensagem', name: 'Mensagem no ecrã' },
			{ variableId: 'modo_web', name: 'Modo de visualização (timer/relogio)' }
		])
	}

	// Lê /status periodicamente para alimentar variáveis usadas nos botões do Stream Deck
	iniciarPolling() {
		if (this.intervaloPoll) {
			clearInterval(this.intervaloPoll)
		}
		if (!this.config.host) return

		const atualizar = async () => {
			try {
				const url = `http://${this.config.host}:${this.config.port || '4545'}/status`
				const resposta = await fetch(url)
				const dados = await resposta.json()
				this.setVariableValues({
					tempo: dados.tempo,
					estado: dados.estado,
					mensagem: dados.mensagem,
					modo_web: dados.modo_web
				})
				this.updateStatus(InstanceStatus.Ok)
			} catch (err) {
				this.updateStatus(InstanceStatus.ConnectionFailure)
			}
		}

		atualizar()
		this.intervaloPoll = setInterval(atualizar, this.config.poll_ms || 500)
	}

	// 3. Regista as ações para aparecerem no menu da Stream Deck
	initActions() {
		this.setActionDefinitions({
			iniciar: {
				name: 'Iniciar Contagem',
				options: [],
				callback: async () => { this.enviarComando('/api/iniciar') }
			},
			pausar: {
				name: 'Pausar Contagem',
				options: [],
				callback: async () => { this.enviarComando('/api/pausar') }
			},
			stop: {
				name: 'Zerar / Stop',
				options: [],
				callback: async () => { this.enviarComando('/api/stop') }
			},
			reset: {
				name: 'Repor Tempo Configurado (Reset)',
				options: [],
				callback: async () => { this.enviarComando('/api/reset') }
			},
			reiniciar: {
				name: 'Reiniciar Tempo (Reset + Play)',
				options: [],
				callback: async () => { this.enviarComando('/api/reiniciar') }
			},
			atualizar: {
				name: 'Aplicar Tempo Digitado (Atualizar)',
				options: [],
				callback: async () => { this.enviarComando('/api/atualizar') }
			},
			modo_web: {
				name: 'Alternar Modo (Timer / Relógio)',
				options: [],
				callback: async () => { this.enviarComando('/api/modo_web') }
			},
			toggle_piscar: {
				name: 'Ativar/Desativar Piscar Pós-Zero',
				options: [],
				callback: async () => { this.enviarComando('/api/toggle_piscar') }
			},
			ecran_on: {
				name: 'Ligar Ecrã de Palco',
				options: [],
				callback: async () => { this.enviarComando('/api/ecran_on') }
			},
			ecran_off: {
				name: 'Desligar Ecrã de Palco',
				options: [],
				callback: async () => { this.enviarComando('/api/ecran_off') }
			},
			mais_hora: {
				name: 'Tempo: +1 Hora',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/mais_hora') }
			},
			menos_hora: {
				name: 'Tempo: -1 Hora',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/menos_hora') }
			},
			mais_min: {
				name: 'Tempo: +1 Minuto',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/mais_min') }
			},
			menos_min: {
				name: 'Tempo: -1 Minuto',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/menos_min') }
			},
			mais_seg: {
				name: 'Tempo: +5 Segundos',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/mais_seg') }
			},
			menos_seg: {
				name: 'Tempo: -5 Segundos',
				options: [],
				callback: async () => { this.enviarComando('/api/tempo/menos_seg') }
			},
			definir_tempo: {
				name: 'Definir Tempo Exato (HH:MM:SS)',
				options: [
					{ type: 'number', id: 'horas', label: 'Horas', default: 0, min: 0, max: 99 },
					{ type: 'number', id: 'minutos', label: 'Minutos', default: 0, min: 0, max: 59 },
					{ type: 'number', id: 'segundos', label: 'Segundos', default: 0, min: 0, max: 59 }
				],
				callback: async (action) => {
					const { horas, minutos, segundos } = action.options
					this.enviarComando(`/api/tempo/set?horas=${horas}&minutos=${minutos}&segundos=${segundos}`)
				}
			},
			fonte_tamanho: {
				name: 'Ajustar Tamanho da Fonte do Palco',
				options: [
					{
						type: 'dropdown',
						id: 'ajuste',
						label: 'Ajuste',
						default: 'plus',
						choices: [
							{ id: 'plus', label: 'Aumentar' },
							{ id: 'minus', label: 'Diminuir' }
						]
					}
				],
				callback: async (action) => {
					this.enviarComando(`/api/fonte/tamanho?ajuste=${action.options.ajuste}`)
				}
			},
			limpar_msg: {
				name: 'Limpar Mensagem do Ecrã',
				options: [],
				callback: async () => { this.enviarComando('/api/limpar_msg') }
			},
			enviar_msg: {
				name: 'Enviar Mensagem Customizada',
				options: [
					{
						type: 'textinput',
						id: 'texto',
						label: 'Mensagem a exibir',
						default: 'INTERVALO'
					}
				],
				callback: async (action) => {
					this.enviarComando(`/api/msg?texto=${encodeURIComponent(String(action.options.texto))}`)
				}
			}
		})
	}

	// Dispara o sinal HTTP em background para o teu painel Python
	async enviarComando(rota) {
		if (!this.config.host) return
		const url = `http://${this.config.host}:${this.config.port || '4545'}${rota}`
		try {
			await fetch(url)
		} catch (err) {
			this.log('error', `Erro ao ligar ao AVK Timer em: ${url}`)
		}
	}
}

runEntrypoint(AVKTimerInstance, [])
