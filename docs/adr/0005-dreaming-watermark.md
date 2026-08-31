# ADR 0005 — Dream híbrido, idempotente e baseado em evidência

Status: aceito.

Decisão: processar após seis horas, com watermark e unicidade por relação; validar toda referência
antes de aplicar, preservar rejeições e recuperar runs interrompidos.

Motivo: resumo a cada turno custa mais, bloqueia chat e reforça erros. Processamento sem watermark
duplica memórias e perde a fronteira temporal.

Consequência: insight não é imediato em modelo sem tools, mas a conversa continua disponível.

