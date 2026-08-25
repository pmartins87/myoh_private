# OpenOFC v5.8.0 — recuperação ativa de identidade

Esta versão transforma uma falha isolada da TableMap em uma transação de
diagnóstico limitada e verificável. Ela não autoriza inferência por semelhança,
não escolhe uma carta provável e não repete entrada física sem evidência.

## Jogo normal

Quando existe exatamente uma carta `UNKNOWN` e uma única origem física atual:

1. o runtime escolhe o próximo slot calibrado e visualmente livre;
2. arrasta a carta lentamente para esse slot;
3. exige uma nova captura válida;
4. aceita a identidade somente se ela for o único elemento novo no board em
   relação ao conjunto físico conhecido antes do movimento;
5. abandona o plano antigo e recalcula a rodada inteira com a carta correta.

A carta fica no board. O executor normal já sabe realocá-la para outra linha ou,
em R1–R4, devolvê-la à área de cartas recebidas caso ela seja o descarte ótimo.

## Fantasy

O scraper conserva evidência diagnóstica mesmo quando rejeita o fan completo.
Se houver exatamente uma transformação de rank/suit inválida, uma única origem
física e uma linha completamente vazia:

1. seleciona somente a carta problemática;
2. usa o botão contextual da linha vazia;
3. lê a carta já colocada no board por diferença exata de conjuntos;
4. grava o conjunto físico completo de 14–17 cartas;
5. clica no `X` da mesma linha;
6. exige uma captura fresca que prove que a linha voltou a ficar vazia;
7. reconstitui o fan por complemento exato e recalcula todo o Fantasy.

Duplicidade, duas cartas não lidas, ausência de linha reversível ou qualquer
desacordo de conjunto continuam `fail-closed`. Nesses casos nenhum clique é
enviado.

## Replay da falha da TM

Cada transação solicita replay BMP + HTML nos pontos relevantes: antes do
movimento, depois da identidade resolvida, após a limpeza do Fantasy e em
timeout/falha. O controlador de replay existente impede duplicata no mesmo
heartbeat.

## Correção adicional de continuidade

Foi corrigida uma falha independente da TableMap: o estado `REACQUIRE` podia
ficar sem transição de saída. Agora ele usa a decisão de liveness já testada:
libera imediatamente quando o estado Hero muda ou, se a entrada física pode ter
sido enviada, após uma janela limitada de oito observações válidas idênticas.

## Escopo da inteligência

O kernel exato de Fantasy 14–17 e o professor exato de R4 da v5.7.0 permanecem
ativos. A recuperação de identidade não muda a função objetivo e não escolhe a
jogada; ela somente entrega ao solver um estado físico comprovado. O próximo
marco matemático é a indução de R3 usando os professores exatos de R4 como
folhas, preservando separadamente informação de dealer/não-dealer, royalties e
re-Fantasy.
