# IPTV Brasil — WCS

Lista com 39 canais selecionados, agrupados em M3U, após as exclusões feitas pelo proprietário. Inclui SBT, Record, Band Rio, RedeTV! Paraná, TV Senado, TV Câmara, ge Fast, N Sports, Gospel Cartoon e canais públicos, educativos, religiosos e regionais.

## Acesso nos aplicativos

Servidor: **https://wcs-tv.walacesssantos.chatgpt.site**

No Prime IPTV ou IPTV Smarters Pro, escolha **Xtream Codes / API** e informe o servidor, usuário e senha recebidos separadamente. A senha não fica neste repositório. O servidor oferece `player_api.php`, `get.php` e caminhos autenticados de transmissão HLS.

Lista M3U direta: https://raw.githubusercontent.com/walacesssantos-TCX/iptv-brasil/main/canais.m3u

SporTV, Premiere, Discovery Turbo e Pluto TV foram retirados. ge Fast foi mantido. Globo RJ segue pendente de uma fonte estável confirmada. Na revisão de 09/10/2026, o candidato M3U retornou 403 e a tentativa anônima no serviço oficial retornou 401; nenhum link foi adicionado.

## Ampliação de esportes

Adicionados 14 canais: Red Bull TV Brasil, FIFA+ (Português), SFT Combat, Desimpedidos, Acelerados, GLORY Kickboxing (FAST), PFL MMA (FAST), RACER Brasil, World Poker Tour (Português), FUEL TV Brasil, Tennis TV Classics, CazéTV, Canal GOAT, Woohoo Surf. ge Fast e N Sports foram mantidos. O relatório de fontes aprovadas e rejeitadas está em `data/verificacao_esportes.json`. O login WCS é do servidor da lista; não substitui logins de emissoras ou plataformas externas. Os canais de marcas com serviços pagos correspondem às versões FAST disponibilizadas publicamente, com programação própria.

## Verificação

O relatório em `data/verificacao_canais.json` registra testes de manifesto HLS, download de segmentos de vídeo e áudio, inspeção com ffprobe e decodificação de um segundo com ffmpeg. A seleção considera os canais que passaram nesses testes em 9 de outubro de 2026. Um teste pontual não garante disponibilidade futura, nem acesso em todas as regiões. A lista contém também WebTVs e afiliadas regionais; não representa todas as emissoras brasileiras.

A Band Rio usa um endereço estável que consulta a configuração pública do player oficial e atualiza seu endereço temporário. Ela passou novamente no teste de manifesto, segmento e decodificação de vídeo H.264 e áudio AAC em 09/10/2026; os resultados desta revisão estão em `data/verificacao_rj.json`. Fontes HTTP usam encaminhamento HTTPS no servidor autenticado. A API utiliza HLS; não converte o vídeo em MPEG-TS. Não há programação EPG nesta versão. O protocolo foi testado automaticamente; a reprodução nos aparelhos Prime e Smarters deve ser conferida no dispositivo.

## API deste repositório

Os arquivos `api/` permitem uma implantação separada em Vercel com as rotas de `vercel.json`. Configure `SESSIONS_JSON` como segredo e `PLAYLIST_URL` como endereço da lista. `.env.example` contém somente exemplos. Gere uma senha local com `node scripts/gerar_login.mjs` e rode os testes com `npm test`. O servidor publicado acima possui implantação e configuração próprias.
