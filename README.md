# IPTV Brasil — WCS

Lista com 32 canais selecionados, agrupados em M3U, preservando a seleção do proprietário e acrescentando a RedeTV! nacional. Inclui SBT, Record, Band Rio, TV Senado, TV Câmara, ge Fast, N Sports, Gospel Cartoon e canais públicos, educativos, religiosos e regionais.

## Acesso nos aplicativos

Servidor: **https://wcs-tv.walacesssantos.chatgpt.site**

No Prime IPTV ou IPTV Smarters Pro, escolha **Xtream Codes / API** e informe o servidor, usuário e senha recebidos separadamente. A senha não fica neste repositório. O servidor oferece `player_api.php`, `get.php` e caminhos autenticados de transmissão HLS e MPEG-TS.

Lista M3U direta: https://raw.githubusercontent.com/walacesssantos-TCX/iptv-brasil/main/canais.m3u

SporTV, Premiere, Discovery Turbo e Pluto TV foram retirados. ge Fast foi mantido. Globo RJ FHD e HD foram incluídas a partir das duas fontes fornecidas pelo proprietário. A FHD foi confirmada em 1920×1080 e a HD em 1280×720, ambas com vídeo H.264 e áudio AAC. Os endereços de reprodução exigem o login WCS; o M3U público atual contém apenas referências ao nosso servidor para esses dois canais.

## Ampliação de esportes

Adicionados 14 canais: Red Bull TV Brasil, FIFA+ (Português), SFT Combat, Desimpedidos, Acelerados, GLORY Kickboxing (FAST), PFL MMA (FAST), RACER Brasil, World Poker Tour (Português), FUEL TV Brasil, Tennis TV Classics, CazéTV, Canal GOAT, Woohoo Surf. ge Fast e N Sports foram mantidos. O relatório de fontes aprovadas e rejeitadas está em `data/verificacao_esportes.json`. O login WCS é do servidor da lista; não substitui logins de emissoras ou plataformas externas. Os canais de marcas com serviços pagos correspondem às versões FAST disponibilizadas publicamente, com programação própria.

## Verificação

O relatório em `data/verificacao_canais.json` registra testes de manifesto HLS, download de segmentos de vídeo e áudio, inspeção com ffprobe e decodificação de um segundo com ffmpeg. A seleção considera os canais que passaram nesses testes em 9 de outubro de 2026. Um teste pontual não garante disponibilidade futura, nem acesso em todas as regiões. A lista contém também WebTVs e afiliadas regionais; não representa todas as emissoras brasileiras.

A Band Rio usa um endereço estável que consulta a configuração pública do player oficial e atualiza seu endereço temporário. Ela passou novamente no teste de manifesto, segmento e decodificação de vídeo H.264 e áudio AAC em 09/10/2026; os resultados desta revisão estão em `data/verificacao_rj.json`. Fontes HTTP usam encaminhamento HTTPS no servidor autenticado. A API utiliza HLS para as fontes HLS e MPEG-TS contínuo para as fontes `.ts`; não há transcodificação. Não há programação EPG nesta versão. O protocolo foi testado automaticamente; a reprodução nos aparelhos Prime e Smarters deve ser conferida no dispositivo.

## Qualidade de imagem e estabilidade

A seleção atual do proprietário tem 32 canais, com 30 fontes HD e 2 fontes de menor resolução. TV Senado permanece em 720p e RedeTV! nacional em 1080p. Os testes de imagem foram realizados antes da seleção mais recente, que removeu dez canais; nenhuma fonte dos canais mantidos foi alterada.

Gospel Cartoon (854×480) e Gospel Movie TV (640×360) seguem na resolução disponível. Mudar o nome para HD não melhora o vídeo original.

Os canais HLS têm uma entrada fixa `/stream/<id>.m3u8`. Globo RJ FHD e HD usam `/live/<usuario>/<senha>/<id>.ts`, com `container_extension: ts` na API Xtream. O servidor consulta a fonte atual, mantém as faixas de áudio e legenda, escolhe perfis HD entre 720p e 1080p e prefere H.264 quando há uma opção HD nesse codec. Fontes sem HD continuam disponíveis em SD. O parâmetro `?quality=auto` permite manter os perfis de menor resolução da fonte. TV Senado e RedeTV! possuem fontes reserva; uma reserva pode ter resolução menor. Os atributos `source-url` e `backup-url` guardam as fontes no M3U, sem usuário ou senha nas fontes públicas. As duas fontes da Globo são referenciadas por `source-key`; suas URLs e alternativas ficam no segredo de ambiente `PRIVATE_CHANNEL_SOURCES_JSON`. CazéTV usa entrega direta por HTTPS em 1080p (HEVC), com a mesma entrada fixa e autenticação; `?quality=auto` escolhe seu manifesto adaptativo. As fontes numéricas HTTP selecionadas usam nomes DNS para o mesmo IP público; o servidor entrega as playlists e os segmentos por HTTPS. Esse encaminhamento também depende da disponibilidade do DNS usado pela fonte.

As três URLs recebidas não reproduziram neste ambiente: GloboNews e RedeTV! retornaram 502; Globo SP expirou por tempo limite. A nova RedeTV! utiliza outra fonte pública testada. Globo SP permanece pendente de um sinal validado; Globo RJ recebeu duas fontes novas, verificadas separadamente. O login WCS não substitui acesso ao Globoplay. Duas URLs anteriores autenticadas da Globo RJ expiraram por tempo limite. Esses resultados históricos não se referem às fontes FHD e HD incluídas nesta atualização. O relatório completo está em `data/verificacao_hd.json`.

A seleção anterior de 40 canais passou no teste de download de segmentos e decodificação de áudio e vídeo, com 37 canais em HD. A seleção atual mantém 30 dessas fontes, com 28 em HD, e acrescenta as duas fontes HD/FHD da Globo. O login foi conferido novamente e retornou conta ativa e catálogo de 32 canais.

Endereços fixos e fontes reserva reduzem a dependência de links temporários, mas não garantem o funcionamento contínuo das emissoras. A qualidade recebida na TV depende também da conexão e do aplicativo.

Na busca anterior na organização `iptv-org`, Globo RJ apareceu em registros de programação (EPG), mas não na lista brasileira de transmissões vigente. As fontes dos registros de inclusão #44697 e #40588 retornaram HTTP 403 nos testes. Nenhum canal Globo foi acrescentado a partir dessas fontes do `iptv-org`. Os detalhes estão em `data/verificacao_iptv_org.json`. Um link anterior autenticado enviado pelo proprietário também retornou HTTP 502; não foi acrescentado e as credenciais foram omitidas. Esse teste está em `data/verificacao_globo_rj.json`.

## Globo RJ no servidor

Globo RJ FHD e Globo RJ HD aparecem separadamente no catálogo Xtream e no M3U autenticado. O servidor encaminha o vídeo original por HTTPS, com um buffer inicial de 256 KiB. O limite de abertura é de 25 segundos; ele não corta a transmissão depois desse tempo. Uma interrupção de 20 segundos encerra a resposta para permitir reconexão pelo aplicativo. Falhas na abertura tentam a alternativa configurada; nas reconexões da mesma instância, a fonte que falhou fica com menor prioridade por um minuto. Se a FHD usar a HD como reserva, a resolução recebida será menor.

A origem redireciona o sinal para outros servidores com IP numérico. O encaminhamento segue esses redirecionamentos no servidor e usa nomes DNS para os mesmos IPs públicos. Não acumula a programação inteira nem mistura os tempos de duas fontes durante a reprodução. O funcionamento depende da origem, desse DNS, da conexão e da reconexão do player; duas URLs do mesmo provedor não garantem continuidade quando ele cai. Não há conversão para HLS ou aumento artificial da resolução. As verificações estão em `data/verificacao_globo_novas.json`.

## Filmes nos aplicativos

O servidor oferece `get_vod_categories`, `get_vod_streams`, `get_vod_info` e reprodução autenticada em `/movie/<usuario>/<senha>/<id>.<extensao>`. Esses recursos alimentam a aba Filmes ao entrar pelo padrão Xtream Codes, sem colocar os títulos na lista de canais ao vivo. Arquivos HTTP usam encaminhamento HTTPS com suporte a pedidos de trecho (Range) e HEAD; fontes HTTPS são entregues diretamente.

A versão atual de `filmes1.m3u` no GitHub contém 1.164 títulos. Foram registrados 288 testes individuais sem um vídeo aprovado; os testes restantes foram interrompidos por bloqueio de rede do ambiente. Isso não comprova que os 1.164 filmes estejam indisponíveis em outras redes. O relatório `data/verificacao_filmes.json` separa registros testados e não testados. O arquivo original `filmes1.m3u` e seu endereço foram preservados.

O catálogo `data/catalogo_filmes.json` contém somente filmes aprovados e não guarda URLs ou senhas do fornecedor. Atualmente está vazio, portanto a aba Filmes ainda não terá títulos reproduzíveis. O servidor consulta a fonte original somente quando houver um filme aprovado.

Para verificar a lista em uma rede que tenha acesso ao fornecedor e gerar o catálogo, execute no repositório com Python e FFmpeg instalados:

```bash
python scripts/verificar_filmes.py --playlist filmes1.m3u --output data/verificacao_filmes.json --catalog data/catalogo_filmes.json --timeout 15 --workers 4
```

Depois de atualizar os dois arquivos de dados no GitHub, recarregue os filmes no aplicativo. O script testa trechos de áudio e vídeo; não verifica a reprodução integral de cada filme.

## API deste repositório

Os arquivos `api/` permitem uma implantação separada em Vercel com as rotas de `vercel.json`. Configure `SESSIONS_JSON` como segredo e `PLAYLIST_URL` como endereço da lista. `.env.example` contém somente exemplos. Gere uma senha local com `node scripts/gerar_login.mjs` e rode os testes com `npm test`. O servidor publicado acima possui implantação e configuração próprias.
