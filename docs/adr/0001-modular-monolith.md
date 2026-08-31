# ADR 0001 — Monólito modular

Status: aceito.

Decisão: um pacote Python e uma imagem, com processos separados para bot, worker e migração. As
fronteiras são módulos internos, não serviços de rede.

Motivo: o MVP precisa de consistência transacional e entrega rápida. Microserviços aumentariam
deploy, observabilidade e falhas distribuídas sem tráfego que as justifique.

Consequência: módulos precisam preservar ownership; separar serviço só após pressão medida de
escala ou ciclo de deploy.

