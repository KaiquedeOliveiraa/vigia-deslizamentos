# VIGIA Deslizamentos

### Sistema Integrado de Monitoramento e Apoio à Decisão para Risco de Deslizamentos

> Projeto Integrador II — UDESC CEAVI

## Sobre o projeto

O **VIGIA Deslizamentos** é um sistema de monitoramento e apoio à decisão voltado à identificação de condições meteorológicas associadas ao risco de deslizamentos de terra nos municípios do Vale Norte, no Alto Vale do Itajaí (SC).

A proposta é integrar dados meteorológicos, geográficos e históricos para apresentar informações de forma simples e visual, auxiliando no acompanhamento das condições de risco por meio de um mapa interativo, indicadores de fácil leitura e notificações via Telegram — tanto para gestores públicos quanto para a população em geral.

O sistema é um **apoio à decisão**, não um emissor de alertas oficiais. Ver a seção [Aviso importante](#aviso-importante).

## Motivação

Deslizamentos de terra estão entre os desastres naturais mais recorrentes e letais no Brasil, especialmente em regiões de relevo acidentado combinadas com chuvas intensas e ocupação irregular de encostas. O caso mais emblemático de Santa Catarina ocorreu em novembro de 2008, quando chuvas prolongadas seguidas de temporais provocaram uma série de deslizamentos no Vale do Itajaí, resultando em mais de cem vítimas fatais e afetando dezenas de municípios da região. Episódios como esse reforçam a importância de sistemas de monitoramento capazes de antecipar cenários de risco e apoiar decisões rápidas por parte da Defesa Civil e da população.

O VIGIA Deslizamentos nasce dessa necessidade: transformar dados dispersos (chuva observada, previsão meteorológica, relevo e histórico de ocorrências) em informação acessível e acionável em escala local.

## Objetivo

Desenvolver um sistema capaz de integrar e analisar dados de precipitação observada e prevista, aplicando a metodologia de cálculo de risco do sistema GeoRisk (Cemaden/MCTI), para fornecer informações que auxiliem no monitoramento e na tomada de decisão diante de possíveis situações de risco de deslizamento nos municípios do Vale Norte.

**Objetivos específicos:**

- Consolidar, em uma única plataforma, dados de precipitação observada, previsão meteorológica e histórico de ocorrências dos seis municípios da área de abrangência;
- Implementar o cálculo do índice de risco conforme a metodologia documentada no Manual Técnico do GeoRisk, com as simplificações declaradas neste documento;
- Classificar automaticamente o nível de risco por município;
- Apresentar os resultados por meio de mapa interativo e painéis de indicadores;
- Notificar usuários inscritos, via Telegram, quando um município atingir nível de risco relevante;
- Estruturar o sistema de forma modular, isolando os parâmetros por município (limiar crítico, meia-vida) da lógica central de coleta, cálculo e visualização.

## Área de abrangência

O escopo está **fechado** na sub-região do **Vale Norte**, dentro do Alto Vale do Itajaí (SC), composta pelos seguintes seis municípios:

| Município | Código IBGE | Observações |
|-----------|-------------|-------------|
| Dona Emma | *a preencher* | |
| Ibirama | *a preencher* | |
| José Boiteux | *a preencher* | |
| Presidente Getúlio | *a preencher* | |
| Vitor Meirelles | *a preencher* | |
| Witmarsum | *a preencher* | |

> Os códigos IBGE devem ser preenchidos a partir da [API de Localidades do IBGE](https://servicodados.ibge.gov.br/api/docs/localidades) e são a chave de identificação de município em todo o sistema (malha geográfica, parâmetros de cálculo e persistência).

A arquitetura isola os parâmetros específicos de cada município (limites geográficos, limiar crítico, meia-vida da água no solo) da lógica central de coleta, processamento e visualização. Isso permite incorporar novos municípios por configuração, mas **a expansão para outras regiões não faz parte do escopo desta versão**.

## Metodologia de cálculo do risco

O cálculo do índice de risco segue a metodologia do **Sistema GeoRisk**, do Cemaden/MCTI, conforme documentado em:

> CAMARINHA, P. I. M. *Metodologia aplicada ao Sistema GeoRisk*. Manual Técnico v.03-2026. Nota Técnica Nº 64/2025/SEI-CEMADEN. Cemaden/MCTI.

O VIGIA **não reproduz integralmente** o GeoRisk: aplica as mesmas equações com um conjunto reduzido de fontes e parâmetros não calibrados. As diferenças estão declaradas em [Simplificações assumidas](#simplificações-assumidas-pelo-vigia).

### Limiar crítico de precipitação

O limiar crítico é o valor mínimo de chuva acumulada que, quando superado, indica possibilidade de deflagração de deslizamentos. No GeoRisk, cada município possui um único limiar de referência, calculado para acumulados de 24 horas e extrapolado para todo o território municipal.

Para municípios não monitorados pelo Cemaden ou sem áreas suscetíveis mapeadas, o GeoRisk adota um limiar hipotético padrão de **250 mm**, e recomenda usar apenas os resultados de análise regional.

No VIGIA, o limiar é um **parâmetro de configuração por município**, versionado no repositório e documentado com a respectiva fonte. A definição dos valores para os seis municípios é uma [decisão em aberto](#decisões-em-aberto).

### Chuva efetiva antecedente

A chuva efetiva antecedente (`EfR`) é a parcela da chuva pretérita que ainda influencia a instabilidade das encostas, calculada sobre as **168 horas (7 dias)** anteriores ao dia-alvo, com decaimento exponencial pelo fator de **meia-vida da água no solo** (`MV`):

$$EfR = \sum_{t=0}^{168} Rh_t \cdot 0{,}5^{\frac{t}{MV}}$$

Onde `Rh` é a chuva horária entre a meia-noite do dia-alvo e as 168 horas anteriores, e `MV` é o parâmetro de decaimento por meia-vida. Na ausência de estudos específicos para o município, o GeoRisk adota **MV = 24 horas** — valor que o VIGIA usa como padrão para os seis municípios.

O período antecedente é preenchido prioritariamente com **dados observados**; onde não houver observação disponível, completa-se com dados de previsão numérica.

### Subíndice de risco

Para cada rodada de previsão numérica disponível, calcula-se um subíndice de risco:

$$SubIR_i = \frac{EfR + Rtotal_{i,\text{dia-alvo}}}{Limiar}$$

Onde `Rtotal` é o total de precipitação acumulada prevista para o dia-alvo (24 horas) pelo respectivo modelo. Um subíndice **maior que 1,0** indica que há possibilidade evidenciada de ocorrerem deslizamentos.

Quando há múltiplos pontos de cálculo dentro de um mesmo município, adota-se o **maior subíndice** encontrado, atribuindo-o ao município inteiro — conforme o procedimento de agregação por polígono do GeoRisk.

### Índice de risco

O índice final combina os `n` subíndices disponíveis por média ponderada, usando a técnica de *time-lagged ensemble* (aproveitando rodadas de até 36 horas antes do momento da análise):

$$\text{Índice de Risco} = \frac{\sum_{i=1}^{n} W_i \cdot SubIR_i}{\sum_{i=1}^{n} W_i}$$

No GeoRisk, os pesos `W` dependem de três fatores: distância temporal da rodada em relação ao momento da análise (rodadas mais recentes pesam mais), presença de assimilação de dados (rodadas 00 UTC e 12 UTC pesam mais que 06 UTC e 18 UTC) e destreza histórica de cada modelo, recalculada periodicamente por matriz de confusão contra ocorrências reais.

### Classes de risco

| Classe | Índice de risco |
|--------|-----------------|
| Extremamente baixo | < 0,40 |
| Muito baixo | 0,40 – 0,70 |
| Baixo | 0,70 – 1,00 |
| Moderado | 1,00 – 1,80 |
| Alto | 1,60 – 2,60 |
| Muito alto | 2,60 – 3,40 |
| Extremamente alto | > 3,40 |

> **Atenção:** o manual técnico apresenta sobreposição entre as classes "moderado" (1,00–1,80) e "alto" (1,60–2,60). A implementação deve adotar um corte único e documentá-lo — ver [Decisões em aberto](#decisões-em-aberto).

O GeoRisk considera "alerta" qualquer resultado com índice maior ou igual a 1,0, correspondente à classe moderado ou superior. O mesmo corte é adotado pelo VIGIA como gatilho de notificação.

### Probabilidades complementares

A partir do percentual de subíndices ponderados que superam determinados valores, o sistema apresenta probabilidades associadas a diferentes magnitudes de evento:

| Evento | Critério |
|--------|----------|
| Deslizamentos pontuais | percentual de subíndices > 1,0 |
| Deslizamentos esparsos | percentual de subíndices > 1,8 |
| Deslizamentos generalizados | percentual de subíndices > 2,6 |

Conforme o manual, essas probabilidades são **informação secundária** — o índice de risco é a referência principal para a tomada de decisão.

### Simplificações assumidas pelo VIGIA

| Aspecto | GeoRisk | VIGIA |
|---------|---------|-------|
| Grade de cálculo | Grade de 5 km × 5 km sobre todo o território nacional | Pontos representativos por município (centróide e pontos adicionais conforme a extensão territorial) |
| Modelos de previsão | 15 a 25 rodadas de GEFS, GFS, WRF, Eta e ECMWF, obtidas direto da fonte | Modelos e ensembles disponibilizados via API pública (a definir na integração) |
| Pesos do ensemble | Recalibrados periodicamente por matriz de confusão contra ocorrências reais | Pesos fixos por recência e horário de assimilação, **sem calibração** |
| Limiar crítico | Calibrado por município pelo Cemaden | Parâmetro de configuração, com fonte documentada |
| Meia-vida (MV) | Valor por município quando há estudo disponível | 24 horas (padrão) para todos os municípios |
| Validação | Matriz de confusão contra o REINDESC (2017–presente) | Sem validação estatística — ver limitações |

### Limitações conhecidas

- **Os pesos do ensemble não são calibrados.** Sem acesso a uma base de ocorrências com cobertura suficiente, não é possível reproduzir o processo de calibração descrito no manual. Os resultados do VIGIA não têm as métricas de POD e FAR do GeoRisk.
- **O limiar crítico é o parâmetro mais sensível da fórmula.** Um limiar incorreto desloca todo o índice. Enquanto os valores não forem obtidos de fonte oficial, os resultados devem ser lidos como demonstração metodológica.
- **A metodologia é de escala regional.** O GeoRisk explicitamente não se propõe a prever a localização exata de deslizamentos em nível de encosta.
- **A resolução da previsão meteorológica é maior que os municípios.** Os modelos globais operam em grades de aproximadamente 25 km — maior que a área de vários dos municípios atendidos. A previsão de chuva praticamente não varia dentro de um mesmo município, o que impede diferenciação intramunicipal a partir de dados de chuva.
- **O sistema tem melhor desempenho para deslizamentos do tipo translacional raso**, conforme o manual.
- **Horários em UTC.** O conceito de "dia-alvo" da metodologia é ancorado em UTC; a conversão para o horário de Brasília (UTC-3) precisa ser tratada explicitamente no cálculo e na exibição.

## Funcionamento

O sistema segue o fluxo:

**Coleta → Tratamento → Cálculo → Classificação → Visualização e notificação**

1. **Coleta:** ingestão de precipitação observada (168 h anteriores) e previsão de precipitação para os dias-alvo, por ponto de cálculo de cada município;
2. **Tratamento:** padronização das séries horárias, preenchimento de lacunas com previsão numérica e associação dos pontos aos municípios;
3. **Cálculo:** chuva efetiva antecedente, subíndices por rodada e índice de risco ponderado;
4. **Classificação:** enquadramento do índice nas classes de risco e cálculo das probabilidades complementares;
5. **Visualização e notificação:** exibição em mapa e painéis, e envio de mensagem via Telegram aos inscritos quando o gatilho é atingido.

O pipeline é executado de forma agendada. A frequência de atualização é uma [decisão em aberto](#decisões-em-aberto).

## Dados e fontes

### Fontes integradas na v1

| Fonte | Tipo de dado | Papel no sistema |
|-------|--------------|------------------|
| **[Open-Meteo](https://open-meteo.com/)** | Previsão de precipitação e histórico horário | Fonte principal de previsão (`Rtotal`) e de chuva observada para compor a chuva efetiva antecedente. API REST gratuita, sem chave para uso não comercial. |
| **[INMET](https://portal.inmet.gov.br/)** — API de estações | Precipitação horária e diária por estação automática | Fonte de observação para comparação e validação da chuva antecedente na região. |
| **[IBGE — Localidades e Malhas](https://servicodados.ibge.gov.br/api/docs/localidades)** | Código, limites municipais e hierarquia geográfica | Identificação dos municípios e polígonos em GeoJSON para o mapa. Consumido uma vez e versionado no repositório. |

### Fontes usadas como dado estático

| Fonte | Tipo de dado | Papel no sistema |
|-------|--------------|------------------|
| **[CPRM / GeoSGB](https://geosgb.cprm.gov.br/)** | Cartas de suscetibilidade a movimentos de massa | Camada informativa de suscetibilidade do terreno. Disponibilizado via WMS/WFS e shapefile — será baixado uma vez, convertido para GeoJSON e versionado, **sem integração automatizada**. |
| **Defesa Civil (municipal/estadual) e [S2iD](https://s2id.mi.gov.br/)** | Histórico de ocorrências e decretos de emergência | Levantamento manual, para compor a base histórica de ocorrências dos seis municípios. |

### Fontes fora do escopo da v1

**CEMADEN (pluviômetros via PED)** e **ANA (HidroWebService)** não serão integradas: a primeira não expõe API REST pública documentada e pode exigir parceria formal; a segunda exige cadastro e trata de variável hidrológica complementar, fora do núcleo da metodologia adotada.

## Funcionalidades previstas

### Interface web

- Mapa interativo com os seis municípios, coloridos pela classe de risco vigente;
- Painel de indicadores gerais (municípios por classe, chuva acumulada, última atualização);
- Detalhamento por município: índice de risco, classe, chuva efetiva antecedente, previsão por dia-alvo, probabilidades complementares e limiar utilizado;
- Camada de suscetibilidade do terreno (CPRM);
- Consulta às fontes e aos dados brutos utilizados em cada análise, com data/hora de coleta;
- Histórico de ocorrências registradas por município.

### Notificação via Telegram

- Inscrição pelo bot (`/start`), com seleção de um ou mais municípios de interesse;
- Envio de mensagem quando um município inscrito atinge índice de risco ≥ 1,0 (classe moderado ou superior);
- Cancelamento da inscrição (`/parar`) e consulta ao status atual (`/status`);
- Controle para não repetir notificação enquanto o município permanecer na mesma classe.

### Camada sub-municipal (condicional)

Tentativa de apresentar diferenciação **dentro** dos municípios, condicionada à disponibilidade de dados.

Como registrado nas limitações, a previsão de chuva não varia na escala intramunicipal destes municípios — portanto, qualquer diferenciação interna deve vir de **características estáticas do terreno** (declividade e suscetibilidade do CPRM), apresentada como *camada de suscetibilidade*, e **não** como um índice de risco por bairro. O índice de risco permanece municipal.

Vale notar que o IBGE não publica malha de bairros para municípios deste porte; o que existe é setor censitário e divisão por distrito/localidade. A viabilidade desta camada deve ser avaliada na etapa de levantamento de dados, e ela **não é requisito obrigatório da v1**.

## Fora do escopo da v1

Registrado explicitamente para evitar ambiguidade na definição dos requisitos:

- Expansão para outros municípios, regiões ou estados, e qualquer interface de seleção de região/estado;
- Emissão de alertas oficiais ou substituição de qualquer produto da Defesa Civil ou do Cemaden;
- Envio por SMS, push, e-mail ou qualquer canal além do Telegram;
- Índice de risco calculado por bairro, encosta ou setor de risco;
- Estimativa de população ou domicílios expostos;
- Calibração dos pesos do ensemble e validação estatística por matriz de confusão;
- Integração automatizada com CEMADEN, ANA e S2iD;
- Área administrativa com autenticação e cadastro de usuários da Defesa Civil.

## Arquitetura

O projeto utiliza a **RADIAN** como arquitetura de referência para a organização do sistema de apoio à decisão.

> *RADIAN: uma proposta de arquitetura de referência de sistemas de suporte à decisão para gerenciamento de desastres naturais.* Universidade Federal de Santa Catarina. Disponível no [Repositório Institucional da UFSC](https://repositorio.ufsc.br/handle/123456789/271363). *(autoria e ano a completar na citação formal)*

A arquitetura orienta a separação dos componentes responsáveis pela aquisição, processamento, integração, análise e apresentação dos dados. Os parâmetros específicos de cada município (limiar, meia-vida, pontos de cálculo, polígono) ficam isolados em configuração, de modo que a inclusão de um município não exija alteração dos módulos centrais.

### RADIAN aplicada ao VIGIA

#### Visão geral da RADIAN

A RADIAN organiza um DSS para desastres naturais em **duas partes**:

- **DSS:** o sistema em si, com **5 blocos**, **13 módulos** e **42 macro funcionalidades**.
- **Ecossistema:** as entidades externas, isto é, os sistemas virtuais e físicos com que o DSS troca dados.

Os 5 blocos do DSS:

| Bloco | Papel |
|---|---|
| Sistema de Interface do Usuário | Interação com usuários em qualquer dispositivo, acessibilidade, personalização |
| Sistemas Cognitivos | Análise, decisão, planejamento e supervisão (malha fechada de controle) |
| Sistemas de Gerenciamento de Dados e Conhecimento | Repositório de dados e de conhecimento |
| Sistemas de Suporte | Governança, manipulação de dados, LGPD, auditoria e relatórios |
| Sistemas de Infraestrutura Computacional | Coleta e ingestão, segurança, colaboração, interoperabilidade |

#### Derivação do VIGIA

A RADIAN é derivada em três passos: arquitetura genérica, depois parcial, depois específica.

| Passo | Definição para o VIGIA |
|---|---|
| **Genérica** | A RADIAN completa (todos os tipos de desastre, 13 módulos, 42 macro funcionalidades) |
| **Parcial** | Desastre **geológico** (movimento de massa / deslizamento) deflagrado por chuva (**meteorológico/hidrológico**). Fases atendidas: **prevenção, preparação e alerta à população**. Usuário sem login. |
| **Específica** | VIGIA Deslizamentos: 6 municípios do Alto Vale do Itajaí, índice GeoRisk diário com previsão de 3 dias, frontend web (GitHub Pages) + backend de coleta/cálculo + bot do Telegram |

#### Visão arquitetural do VIGIA

```
┌──────────────────────────────── DSS: VIGIA ───────────────────────────────┐
│ INTERFACE DO USUÁRIO                                                      │
│  Rail/barra inferior · Cabeçalho · PT/ES · Acessibilidade · 7 telas       │
├───────────────────────────────────────────────────────────────────────────┤
│ SISTEMAS COGNITIVOS                                                       │
│  Análise e Tomada de Decisão ── Monitoramento, Dados da análise,          │
│                                 Simulação, Previsões D0–D3                │
│  Supervisão da Execução ─────── Alertas (bot Telegram), Contatos          │
├───────────────────────────────────────────────────────────────────────────┤
│ DADOS E CONHECIMENTO                                                      │
│  Dados: índices, séries, acumulados, malhas, estações                     │
│  Conhecimento: Cartilha, classes GeoRisk, i18n                            │
├───────────────────────────────────────────────────────────────────────────┤
│ SUPORTE                        │ INFRAESTRUTURA COMPUTACIONAL             │
│  LGPD (sem dado pessoal no     │  Coleta/ingestão (Open-Meteo, INMET)     │
│  site; bot guarda só chat_id)  │  Interoperabilidade (IBGE, iframe SC,    │
│                                │  Google Maps, Telegram) · HTTPS          │
└───────────────────────────────────────────────────────────────────────────┘
                                   ▲ ▼
┌──────────────────────────────── ECOSSISTEMA ──────────────────────────────┐
│ Sistemas virtuais: Open-Meteo · IBGE (malhas, Localidades) · Cemaden      │
│   (GeoRisk, estações) · Defesa Civil SC (mapa oficial) · INMET ·          │
│   Epagri/Ciram · Telegram · Google Maps · OpenStreetMap                   │
│ Sistemas físicos: pluviômetros, réguas de rio, estações meteorológicas;   │
│   áreas de encosta dos 6 municípios                                       │
│ Atores externos: população, coordenadorias municipais de Defesa Civil,    │
│   SDC-SC, serviços de emergência (199, 193, 192)                          │
└───────────────────────────────────────────────────────────────────────────┘
```

#### Macro funcionalidades RADIAN usadas

| Bloco / Módulo RADIAN | Macro funcionalidade | Onde está no VIGIA |
|---|---|---|
| Interface do Usuário / Gestão da Interface | Gestão de Interação com os Usuários | Rail, cabeçalho, PT/ES, painel de Acessibilidade, temas, paletas, anúncios `aria-live` |
| Interface do Usuário / Usuários | Modo Treinamento & Capacitação | Cartilha (educação da população); Simulação como ambiente fechado |
| Cognitivos / Análise e Tomada de Decisão | Visualização de Dados e Painéis de Decisão | Monitoramento (mapa + painel), Dados da análise (indicadores, gráfico, pluviômetro, tabela) |
| Cognitivos / Análise e Tomada de Decisão | Avaliação e Mapeamento de Vulnerabilidades | Mapa por classe GeoRisk com hachura; limiar crítico por município |
| Cognitivos / Análise e Tomada de Decisão | Predição de Cenários | Previsões D0–D3 (Open-Meteo) |
| Cognitivos / Análise e Tomada de Decisão | Geração e Simulação de Cenários de Decisão | Simulação "E se chover…?" |
| Cognitivos / Análise e Tomada de Decisão | Diagnóstico | Painel do município: índice, classe, chuva/limiar, estado de alerta |
| Cognitivos / Análise e Tomada de Decisão | FAQ (Perguntas Frequentes) | Cartilha (sinais, o que fazer, mochila, não faça) |
| Cognitivos / Supervisão da Execução | Geração e Envio de Alertas | Bot do Telegram (aviso quando o município entra em alerta) |
| Cognitivos / Supervisão da Execução | Comunicação entre Atores | Contatos (199, 193, 192, SMS 40199, Defesa Civil municipal) e Compartilhar |
| Dados e Conhecimento | Acesso e Gerenciamento de Dados | Índices, séries de 7 dias, acumulados, malhas IBGE, estações |
| Dados e Conhecimento | Acesso e Gerenciamento de Conhecimento | Classes GeoRisk, conteúdo da Cartilha, dicionário PT→ES |
| Suporte | LGPD e Privacidade de Dados | Site sem coleta de dado pessoal; bot guarda só `chat_id` e municípios |
| Infraestrutura | Coleta, Ingestão e Processamento Estatístico de Dados | Coleta de previsão/chuva (Open-Meteo) e cálculo do índice |
| Infraestrutura | Segurança Computacional | HTTPS, links externos com `rel="noopener"`, sem segredo no front-end |
| Infraestrutura (Interoperabilidade) | Comunicação com Sistemas Ciberfísicos e Infraestruturas | Estações (pluviômetro, régua, meteorológica) — v1 só localização |
| Ecossistema | Sistemas dos Atores Externos | Open-Meteo, IBGE, Cemaden, Defesa Civil SC, INMET, Epagri/Ciram, Telegram, Google Maps |

#### Módulos RADIAN fora do escopo

| Módulo / Macro funcionalidade | Situação | Motivo |
|---|---|---|
| Planejamento da Execução (ações, parceiros, projetos, abrigos, inventário, doações, resgates, recursos, restauração, recuperação, contingência) | Não se aplica | O VIGIA não gerencia resposta a desastre |
| Suporte à Decisão Multicritério, Análise e Decisão de Alternativas, Solução de Problemas | Não se aplica | O índice é único (GeoRisk); não há escolha entre alternativas |
| Discussão Colaborativa Distribuída / Plataforma Colaborativa | Não se aplica | Sem usuários autenticados nem salas de decisão |
| Supervisão e Monitoramento das Ações, Gestão e Coordenação de Ações | Não se aplica | Não há ações de resposta registradas |
| Governança, Auditoria, Geração de Relatórios | Futuro | Só faz sentido com uma área restrita para a Defesa Civil |
| Assistente Digital | Futuro | Pode evoluir a partir do bot do Telegram |
| Gêmeo Digital, Big Data, Manipulação de Dados e Machine Learning | Futuro | Depende de séries históricas e dados de campo |
| Atuação sobre Sistemas Físicos | Não se aplica | O VIGIA só observa |

**Componentes principais:**

| Componente | Responsabilidade |
|------------|------------------|
| Coletor | Consumo das APIs de precipitação observada e prevista |
| Processador | Cálculo da chuva efetiva antecedente, subíndices e índice de risco |
| Classificador | Enquadramento nas classes e cálculo das probabilidades complementares |
| Persistência | Armazenamento das séries, dos índices calculados e dos inscritos do bot |
| API | Exposição dos resultados ao frontend |
| Notificador | Bot do Telegram: inscrição, disparo e controle de repetição |
| Interface | Mapa, painéis e consulta aos dados |

## Especificação do sistema

Especificação funcional derivada do protótipo navegável e organizada pelos viewpoints da RADIAN (Negócio, Uso, Funcional, Implementação). A coluna **RADIAN** das tabelas indica a macro funcionalidade de origem (ver [Arquitetura](#arquitetura)).

### Glossário

| Termo | Significado |
|---|---|
| Índice de risco | Valor contínuo (≥ 0) calculado pela metodologia GeoRisk a partir da chuva efetiva e do limiar do município |
| Classe | Faixa do índice (1 a 7), de "extremamente baixo" a "extremamente alto" |
| Em alerta | Município com índice ≥ 1,00 (classe moderado ou acima) |
| Dia-alvo | Data de referência dos índices exibidos (D0, "hoje") |
| D1–D3 | Previsões para +1, +2 e +3 dias |
| Chuva efetiva antecedente | Chuva acumulada ponderada usada no cálculo do índice (mm) |
| Limiar crítico | Chuva a partir da qual o município tende a ter deslizamentos (mm); parâmetro de configuração por município |
| Membros de ensemble | Número de rodadas do modelo de previsão usadas na estimativa |
| Paleta GeoRisk / Acessível | Cores das classes: a do GeoRisk ou uma alternativa segura para daltonismo |

### Viewpoint de Negócio

#### Stakeholders

| Stakeholder | Interesse | O que espera do VIGIA |
|---|---|---|
| População dos 6 municípios | Saber se há risco perto de casa e o que fazer | Tela simples, idioma próprio, aviso no celular, número de emergência à mão |
| Coordenadorias municipais de Defesa Civil | Acompanhar o risco e orientar a população | Índice por município, previsão, evolução, chuva vs. limiar, contatos corretos |
| Secretaria de Estado da Proteção e Defesa Civil (SDC-SC) | Uso correto e creditado do mapa oficial | Crédito visível, link para o site oficial, autorização para incorporar |
| Cemaden | Uso fiel da metodologia GeoRisk | Mesmas classes, faixas e nomes; aviso de que não é alerta oficial |
| Pessoas com deficiência, falantes de espanhol | Acesso em igualdade | Leitor de tela, teclado, alto contraste, paleta para daltonismo, Español |
| Equipe do projeto | Construir e manter o sistema | Especificação clara, protótipo de referência, design system |

#### Objetivos

| ID | Objetivo |
|---|---|
| OBJ-01 | Mostrar o risco de deslizamento de hoje e dos próximos 3 dias para os 6 municípios, de forma compreensível em segundos |
| OBJ-02 | Permitir que a pessoa entenda o efeito de uma chuva esperada sobre o risco (simulação) |
| OBJ-03 | Levar a população a agir: reconhecer sinais, saber o que fazer e a quem ligar |
| OBJ-04 | Entregar avisos no celular (Telegram) quando um município entrar em alerta |
| OBJ-05 | Ser acessível a todos (WCAG 2.1 AA, PT/ES, alto contraste, daltonismo) |
| OBJ-06 | Deixar claro que o sistema é de apoio e não substitui os canais oficiais |

### Viewpoint de Uso

Cenários de uso. Ator padrão: **cidadão** (sem login).

| ID | Cenário | Fluxo principal | Telas |
|---|---|---|---|
| UC-01 | Consultar o risco de hoje | Abre o site → vê o mapa colorido e "N de 6 em alerta" → toca no seu município → lê índice, classe e estado de alerta no painel | Monitoramento |
| UC-02 | Ver a previsão | No Monitoramento, escolhe +1d/+2d/+3d ou aperta play → o mapa e o painel mostram os valores estimados com a faixa "Previsão" | Monitoramento |
| UC-03 | Achar um município pelo nome | Toca na lupa → digita (sem precisar de acento) → Enter ou toque → município selecionado e piscando | Monitoramento |
| UC-04 | Simular uma chuva | No painel, "Simular chuva" (ou menu Simulação) → escolhe período e mm (ou atalho) → Simular → vê o mapa recolorir, a comparação agora→simulado e o aviso | Simulação |
| UC-05 | Entender a tendência | Abre Dados da análise → vê indicadores, gráfico de 7 dias e pluviômetro → clica em outro município na tabela ou nos chips | Dados da análise |
| UC-06 | Receber avisos no Telegram | Toca em "Alertas no Telegram" (ou no botão do painel/banner) → "Abrir no Telegram" → no bot, toca Iniciar e escolhe municípios → recebe aviso quando algum entrar em alerta → `/parar` para sair | Todas + bot |
| UC-07 | Aprender a se proteger | Abre Cartilha → vira os cartões de sinais → vê Antes/Durante/Depois → marca a mochila → lê "Não faça" | Cartilha |
| UC-08 | Pedir ajuda / achar a Defesa Civil | Toca em 199 (ou "Emergência? Ver contatos") → liga, ou filtra o município → "Como chegar" / "Copiar telefone" | Contatos |
| UC-09 | Consultar o mapa oficial de SC | Abre Monitoramento SC → vê o mapa incorporado ou, se bloqueado, abre em nova aba | Monitoramento SC |
| UC-10 | Ver onde ficam as estações | Abre Estações → toca num pin ou item da lista → vê tipo, município, fonte e coordenadas | Estações |
| UC-11 | Ajustar acessibilidade | Toca no ícone de acessibilidade → escolhe idioma, tema e cores do mapa → preferência lembrada na próxima visita | Todas |
| UC-12 | Compartilhar o risco | No painel do município, "Compartilhar" → texto com município, classe e índice vai para a área de transferência | Monitoramento |

### Viewpoint Funcional — Requisitos Funcionais

Prioridade: **A** = essencial para a v1 · **M** = desejável · **B** = pode ficar para depois.
Coluna RADIAN: macro funcionalidade de origem.

#### Elementos globais (GLB)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-GLB-01 | Exibir menu de navegação com as 7 telas, na ordem: Monitoramento, Simulação, Dados da análise, Monitoramento SC, Estações, Cartilha, Contatos. No desktop, rail lateral de 64px (só ícones, nome em tooltip) que expande para 232px pelo botão hambúrguer, sobrepondo o conteúdo; abaixo de 900px, barra inferior com rótulos curtos (Mapa, Simular, Dados, SC, Estações, Cartilha, Contatos). | A | Gestão de Interação |
| RF-GLB-02 | Marcar a tela ativa no menu (fundo, ícone e barra em laranja, `aria-current="page"`). | A | Gestão de Interação |
| RF-GLB-03 | Exibir cabeçalho com marca VIGIA, região ("Vale Norte — Alto Vale do Itajaí, SC"), dia-alvo e horário da última atualização. | A | Visualização de Dados |
| RF-GLB-04 | Permitir trocar o idioma entre Português e Español pelo seletor PT/ES do cabeçalho e pelo painel de Acessibilidade, traduzindo toda a interface e o atributo `lang`. | A | Gestão de Interação |
| RF-GLB-05 | Abrir o painel de Acessibilidade (botão no cabeçalho e no rodapé do rail) com: idioma; tema Automático / Claro / Escuro / Alto contraste; cores do mapa GeoRisk / Acessível (daltonismo). | A | Gestão de Interação |
| RF-GLB-06 | Guardar idioma, tema e paleta no navegador e reaplicá-los na próxima visita. | M | Gestão de Interação |
| RF-GLB-07 | Exibir o botão "Alertas no Telegram" no cabeçalho de todas as telas, abrindo a janela do Telegram (RF-TG-01). | A | Geração e Envio de Alertas |
| RF-GLB-08 | Oferecer o link "Pular para o conteúdo" como primeiro elemento focável. | A | Gestão de Interação |
| RF-GLB-09 | Anunciar por região `aria-live` as mudanças relevantes: seleção de município, dia de previsão, resultado da simulação, troca de idioma/tema/paleta, cópia de texto. | A | Gestão de Interação |
| RF-GLB-10 | Mostrar em toda tela com índice o aviso "Sistema de apoio à decisão… Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil." | A | Diagnóstico |

#### Monitoramento (MON)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-MON-01 | Exibir o mapa dos 6 municípios (malha IBGE), cada um preenchido pela cor da classe do índice do dia selecionado; municípios vizinhos em cinza com nome, como contexto. | A | Visualização de Dados; Mapeamento de Vulnerabilidades |
| RF-MON-02 | Exibir, sobre cada município, um rótulo com selo da classe (cor + ícone), nome, índice e nome da classe. | A | Visualização de Dados |
| RF-MON-03 | Aplicar hachura aos municípios de classe moderado ou acima, mais densa quanto maior a classe (RN-04). | A | Mapeamento de Vulnerabilidades |
| RF-MON-04 | Permitir selecionar um município por clique, toque, busca ou teclado (Tab + Enter/Espaço). O selecionado recebe contorno grosso e vem para frente. Município inicial: o de maior índice (no protótipo, Ibirama). | A | Gestão de Interação |
| RF-MON-05 | Exibir o painel do município selecionado com: nome; estado "Em alerta"/"Sem alerta" com a classe; índice grande com selo; chuva efetiva antecedente (mm, com barra); limiar crítico (mm); razão chuva/limiar (com barra); membros de ensemble; aviso de RF-GLB-10. | A | Diagnóstico |
| RF-MON-06 | Exibir o resumo "N de 6 municípios em alerta · maior índice X" para o dia selecionado. | A | Visualização de Dados |
| RF-MON-07 | Exibir o cartão Previsões com o dia-alvo ("hoje") e +1d, +2d, +3d; permitir escolher o dia, voltar, avançar (cíclico) e reproduzir/pausar (avança ~1 s por dia). Mapa, resumo e painel passam a mostrar os valores do dia escolhido. | A | Predição de Cenários |
| RF-MON-08 | Em dia de previsão, exibir a faixa "Previsão · dd/mm/aa — valores estimados" sobre o mapa e indicar "previsão dd/mm/aa" no painel. | A | Predição de Cenários |
| RF-MON-09 | Exibir a legenda recolhível (RF-LEG-01 a 05). | A | Visualização de Dados |
| RF-MON-10 | Exibir a busca de município (RF-BUS-01 a 04); ao escolher, selecionar e fazer o município piscar 2 vezes. | A | Gestão de Interação |
| RF-MON-11 | Botão "Compartilhar": copiar texto/link "Município — classe (índice)" e confirmar com aviso temporário (~2 s). Na implementação, usar a Web Share API quando disponível e cair para cópia. | M | Comunicação entre Atores |
| RF-MON-12 | Botão "Simular chuva": abrir a Simulação com o município já selecionado. | A | Geração e Simulação de Cenários |
| RF-MON-13 | Botão "Receber alertas de <município> no Telegram": abrir a janela do Telegram com o link já apontando para esse município. | A | Geração e Envio de Alertas |
| RF-MON-14 | Controles de zoom (+/−) e seletor de camada base (Satélite, Neutro, Ruas, Relevo). | M | Visualização de Dados |

##### Legenda recolhível (LEG)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-LEG-01 | Exibir a legenda recolhida como faixa de 32px com as 7 cores + "não monitorado", do maior risco para o menor. | A | Visualização de Dados |
| RF-LEG-02 | Abrir o cartão da legenda ao passar o mouse, focar ou tocar na faixa; fechar ao sair, se não estiver fixada. | A | Gestão de Interação |
| RF-LEG-03 | Botão cadeado fixa/destrava o cartão aberto; botão × recolhe e destrava. | M | Gestão de Interação |
| RF-LEG-04 | O cartão lista as 7 classes (selo, nome, faixa) + "não monitorado" e a regra "Alerta a partir de 1,00 (moderado). Classes com hachuras no mapa: moderado ou acima." | A | Acesso ao Conhecimento |
| RF-LEG-05 | O cartão permite trocar a paleta GeoRisk / Acessível, sincronizada com o painel de Acessibilidade. | A | Gestão de Interação |

##### Busca de município (BUS)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-BUS-01 | Botão redondo de lupa no canto inferior do mapa abre um campo "Buscar município…". | A | Gestão de Interação |
| RF-BUS-02 | Filtrar os municípios sem diferenciar acento nem maiúsculas ("jose" encontra José Boiteux), destacando o trecho encontrado. Cada resultado mostra selo, nome, classe e índice. | A | Gestão de Interação |
| RF-BUS-03 | Teclado: ↑/↓ navega, Enter escolhe, Esc fecha. | A | Gestão de Interação |
| RF-BUS-04 | Sem resultado: "Nenhum município monitorado com esse nome." | A | Gestão de Interação |

#### Simulação (SIM)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-SIM-01 | Formulário com: município (lista; pré-selecionado quando vier do Monitoramento); período (próximas 24 h, 48 h, 72 h; padrão 48 h); chuva esperada em mm por controle deslizante (0–250) e campo numérico (0–400) sincronizados; atalhos fraca 10, moderada 30, forte 60, muito forte 100, extrema 180 mm. | A | Geração e Simulação de Cenários |
| RF-SIM-02 | Opção "Aplicar a mesma chuva aos 6 municípios (chuva regional)". | M | Geração e Simulação de Cenários |
| RF-SIM-03 | Botão "Simular": calcular o índice simulado (RN-09), recolorir o mapa com animação de 0,6 s, selecionar e fazer piscar o município. | A | Geração e Simulação de Cenários |
| RF-SIM-04 | Exibir o resultado: comparação "Agora → Simulado" (índice e classe com selo); escala contínua 0–4 com marcadores "agora" e "simulado" e marcas 1,00 alerta e 2,60; chuva efetiva atual, chuva efetiva simulada e limiar crítico. | A | Análise de Cenários |
| RF-SIM-05 | Exibir sobre o mapa o aviso do resultado em três níveis (RN-10); com chuva regional, um segundo aviso "Chuva regional: N de 6 em alerta" listando os municípios que passariam de 1,00. | A | Geração e Simulação de Cenários |
| RF-SIM-06 | Alternar a visualização do mapa entre "Agora" e "Simulado" sem refazer o cálculo. | A | Visualização de Dados |
| RF-SIM-07 | Botão "Voltar à condição atual" limpa resultado, aviso e mapa simulado. | A | Gestão de Interação |
| RF-SIM-08 | Exibir cartão "Condição atual · data hora" ou "Cenário simulado" com "N de 6 municípios em alerta". | A | Visualização de Dados |
| RF-SIM-09 | Clicar num município no mapa o seleciona no formulário. | M | Gestão de Interação |
| RF-SIM-10 | Exibir a legenda recolhível e o zoom, como no Monitoramento. | M | Visualização de Dados |

#### Dados da análise (DAD)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-DAD-01 | Exibir 4 indicadores: municípios monitorados; em alerta (índice ≥ 1,0); chuva efetiva máxima (mm, com município); pico da semana (índice, município e data). | A | Visualização de Dados |
| RF-DAD-02 | Exibir o gráfico "Evolução do índice" dos últimos N dias do município em destaque: faixas de fundo pelas classes; linha tracejada "ALERTA 1,00"; pontos coloridos pela classe do dia; variação diária sobre cada ponto (+ em vermelho, − em verde); marca "↑ classe"/"↓ classe" quando muda de classe; demais municípios como linhas cinza finas. | A | Visualização de Dados |
| RF-DAD-03 | Chips com os 6 municípios para trocar o destaque do gráfico. | A | Gestão de Interação |
| RF-DAD-04 | Exibir o pluviômetro "Chuva acumulada" do município em destaque: 4 tubos (24 h, 48 h, 72 h, 96 h), escala fixa 0–150 mm, linha tracejada do limiar crítico, etiqueta "choveu nas últimas 24h" ou "sem chuva agora" (RN-14). | A | Visualização de Dados |
| RF-DAD-05 | Exibir a tabela "Índice por município": município, índice, classe (selo + nome), variação 24 h (seta + valor), minigráfico dos últimos 7 dias, chuva efetiva / limiar (valor + barra), alerta (sim/não). Clicar numa linha troca o destaque do gráfico e do pluviômetro. | A | Visualização de Dados |
| RF-DAD-06 | Seletor de período 7 / 5 / 15 dias para o gráfico e o minigráfico. (No protótipo só 7 dias funciona.) | M | Visualização de Dados |

#### Monitoramento SC (SC)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-SC-01 | Exibir cartão explicativo do mapa oficial da SDC-SC e botão "Abrir em nova aba" para `https://monitoramento.defesacivil.sc.gov.br/mapa`. | A | Sistemas dos Atores Externos |
| RF-SC-02 | Incorporar o mapa oficial via `iframe` com barra de título, URL e rodapé de crédito da fonte. | M | Interoperabilidade |
| RF-SC-03 | Se a incorporação for bloqueada ou falhar, mostrar o plano B: "O mapa não pôde ser carregado aqui…" com o botão "Abrir mapa oficial". | A | Interoperabilidade |

#### Estações (EST)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-EST-01 | Exibir mapa com os 6 municípios sem cor de risco, com o nome escrito, e um pin por estação posicionado por latitude/longitude. | A | Comunicação com Sistemas Ciberfísicos |
| RF-EST-02 | Exibir lista lateral com cada estação: tipo (Pluviômetro, Régua de rio, Estação meteorológica), nome/local, município, fonte e coordenadas. | A | Acesso a Dados |
| RF-EST-03 | Selecionar uma estação pelo pin (clique, toque, Tab + Enter) ou pela lista; o pin fica laranja e abre um balão com nome, tipo, município e coordenadas. Selecionar de novo desmarca. | A | Gestão de Interação |
| RF-EST-04 | Controles de zoom. | M | Visualização de Dados |
| RF-EST-05 | (Evolução) Mostrar a chuva das últimas 24 h e o nível do rio de cada estação. | B | Coleta e Ingestão de Dados |

#### Cartilha (CAR)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-CAR-01 | Exibir cabeçalho "Deslizamento: como se proteger" e o botão grande "199 · Emergência? Ver contatos", que leva à tela Contatos. | A | FAQ; Comunicação entre Atores |
| RF-CAR-02 | Navegação por âncoras "1. Sinais · 2. O que fazer · 3. Mochila · 4. Não faça", com rolagem suave e destaque da seção visível. | A | Gestão de Interação |
| RF-CAR-03 | Seção **Sinais de perigo**: 6 cartões ilustrados (rachaduras novas; portas e janelas emperrando; árvores e postes inclinando; água barrenta minando; estalos e barulhos; muro estufado) que viram ao toque e mostram "Saia do local agora · Depois ligue 199". | A | Treinamento & Capacitação |
| RF-CAR-04 | Seção **O que fazer**: abas Antes / Durante / Depois (setas ←/→), cada uma com 4 blocos de ícone + frase. | A | Treinamento & Capacitação |
| RF-CAR-05 | Seção **Mochila de emergência**: 8 itens (documentos, lanterna, rádio e pilhas, remédios, água, carregador, roupa e agasalho, apito) marcáveis ao toque, com barra de progresso "N de 8" e "Mochila pronta!" ao completar. | M | Treinamento & Capacitação |
| RF-CAR-06 | Seção **Não faça**: 6 blocos com ícone riscado (lixo no barranco, esgoto na encosta, cortar o barranco, desmatar a encosta, bananeira na encosta, construir na beira do barranco). | A | Treinamento & Capacitação |
| RF-CAR-07 | Banner do Telegram no fim da página e citação das fontes (Defesa Civil RJ, SP Sempre Alerta). | A | Geração e Envio de Alertas |

#### Contatos (CON)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-CON-01 | Exibir os números de emergência em cartões grandes e clicáveis: 199 Defesa Civil (em destaque), 193 Bombeiros, 192 SAMU (`tel:`), 40199 SMS com CEP para receber alertas (`sms:`). | A | Comunicação entre Atores |
| RF-CON-02 | Exibir o banner do Telegram. | A | Geração e Envio de Alertas |
| RF-CON-03 | Filtro "Seu município": destaca o cartão escolhido, esmaece os demais e rola até ele. | M | Gestão de Interação |
| RF-CON-04 | Exibir um cartão por município com: nome; selo "verificado"/"a confirmar"; coordenador(a) municipal de Defesa Civil; telefone; e-mail; endereço. | A | Comunicação entre Atores |
| RF-CON-05 | Botão "Como chegar" abre o Google Maps (`https://www.google.com/maps/search/?api=1&query=<endereço>`) em nova aba. | A | Interoperabilidade |
| RF-CON-06 | Botão "Copiar telefone" (confirma "Copiado"); sem telefone, mostra "Site da prefeitura" no lugar. | A | Comunicação entre Atores |

#### Alertas no Telegram (TG)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-TG-01 | Janela "Receba os alertas no Telegram": explicação em 3 linhas (aviso quando um município entrar em alerta; você escolhe os municípios no bot; grátis, para sair envie /parar), botão "Abrir no Telegram", nome do bot com botão copiar e prévia da primeira mensagem do bot com o teclado de municípios. | A | Geração e Envio de Alertas |
| RF-TG-02 | Portas de entrada: botão do cabeçalho, botão do painel do município (RF-MON-13) e banner na Cartilha e em Contatos. | A | Gestão de Interação |
| RF-TG-03 | Link `https://t.me/<bot>`; aberto a partir de um município, `?start=<slug>` (ibi, pgt, jbx, dem, wit, vme). | A | Geração e Envio de Alertas |
| RF-TG-04 | Bot: `/start [slug]` saúda e sugere o município do slug; teclado inline com os 6 municípios + "Todos" para escolher; `/municipios` para rever a escolha; `/status` mostra a situação atual dos municípios inscritos; `/parar` cancela a inscrição. | A | Geração e Envio de Alertas |
| RF-TG-05 | Bot: enviar aviso a cada inscrito conforme RN-17, com texto condicional, índice, classe e link para o VIGIA. | A | Geração e Envio de Alertas |

#### Previstas sem tela no protótipo (EXT)

| ID | Requisito | Prior. | RADIAN |
|---|---|---|---|
| RF-EXT-01 | No painel do município, exibir as probabilidades complementares: deslizamentos pontuais (% de subíndices > 1,0), esparsos (> 1,8) e generalizados (> 2,6), como informação secundária ao índice. | M | Predição de Cenários |
| RF-EXT-02 | No painel do município, exibir o limiar utilizado e sua fonte. | A | Diagnóstico |
| RF-EXT-03 | Camada informativa de suscetibilidade do terreno (CPRM/GeoSGB), ligável no mapa, sem virar índice por bairro. | B | Mapeamento de Vulnerabilidades |
| RF-EXT-04 | Consulta às fontes e aos dados brutos de cada análise, com data/hora de coleta. | M | Acesso e Gerenciamento de Dados |
| RF-EXT-05 | Histórico de ocorrências registradas por município (levantamento manual Defesa Civil/S2iD). | M | Acesso e Gerenciamento de Conhecimento |

### Requisitos Não Funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF-01 | Acessibilidade | Atender WCAG 2.1 nível AA. Nenhuma violação séria ou crítica no axe-core nos 3 temas (claro, escuro, alto contraste) e nos 2 idiomas, verificada antes de cada publicação. |
| RNF-02 | Acessibilidade | Contraste de texto ≥ 4,5:1 (≥ 7:1 no tema Alto contraste); ícone da classe ≥ 3:1 sobre a cor da classe; texto do botão primário em `on-accent` (escuro), nunca branco sobre laranja. |
| RNF-03 | Acessibilidade | Todo o sistema operável por teclado: foco visível de 3px; municípios e pins focáveis; janelas com foco preso, Esc fecha e devolve o foco; abas com setas. |
| RNF-04 | Acessibilidade | Estrutura semântica por tela: `nav`, `main`, um `h1`; controles com rótulo acessível; ilustrações decorativas com `aria-hidden`. |
| RNF-05 | Acessibilidade | Respeitar `prefers-reduced-motion` (sem animações de recolorir, piscar ou rolar). |
| RNF-06 | Usabilidade | Alvos de toque ≥ 44 × 44 px; nada depende só de hover. |
| RNF-07 | Responsividade | Layout funcional de 320 px até desktop sem rolagem horizontal; abaixo de 900 px o rail vira barra inferior e o painel do município vai para baixo do mapa. |
| RNF-08 | Internacionalização | PT-BR e ES completos, com rotas ou chaves de tradução (não substituição sobre o DOM). Números com vírgula decimal nos dois idiomas. Marcadores `{M}` município, `{C}` classe, `{N}` número. |
| RNF-09 | Desempenho | Meta: LCP ≤ 2,5 s e CLS ≤ 0,1 em celular 4G (Core Web Vitals "bom"). Troca de dia de previsão e simulação em ≤ 100 ms (cálculo local). |
| RNF-10 | Disponibilidade | Frontend estático (GitHub Pages) consumindo a API do backend. Se a atualização de dados falhar, o site continua servindo o último índice válido com seu dia-alvo e horário, sem esconder a data. |
| RNF-11 | Privacidade (LGPD) | O site não coleta dado pessoal nem usa cookies de rastreamento; preferências ficam só no `localStorage` do navegador. O bot guarda apenas `chat_id` e municípios escolhidos; `/parar` apaga o registro (política final de retenção: ver decisão 8). |
| RNF-12 | Segurança | Somente HTTPS; links externos com `target="_blank" rel="noopener"`; nenhum token (ex.: do bot) no código do front-end ou no repositório. |
| RNF-13 | Compatibilidade | Duas últimas versões de Chrome, Edge, Firefox e Safari; Chrome Android e Safari iOS. |
| RNF-14 | Robustez | Se `localStorage` ou `navigator.clipboard` não estiverem disponíveis, o sistema funciona com os padrões (Português, tema automático, paleta GeoRisk) e sem quebrar. |
| RNF-15 | Manutenibilidade | Uma rota/componente por tela; cores, tipografia e espaçamentos só por tokens do design system (CSS custom properties); dados de municípios, estações e contatos em arquivos de dados, não no código. |
| RNF-16 | Transparência | Fonte de cada dado citada na tela (Open-Meteo, IBGE, Cemaden, SDC-SC, cartilhas de referência). |
| RNF-17 | Escalabilidade | Adicionar um município deve exigir só dados (polígono IBGE, limiar, contatos, estações), sem mudar componentes. (A expansão para outras regiões está fora do escopo da v1.) |

### Regras de Negócio

| ID | Regra |
|---|---|
| RN-01 | **Classes GeoRisk** (limite inferior incluído na classe de cima): 1 extremamente baixo < 0,40 · 2 muito baixo 0,40–0,70 · 3 baixo 0,70–1,00 · 4 moderado 1,00–1,80 · 5 alto 1,80–2,60 · 6 muito alto 2,60–3,40 · 7 extremamente alto > 3,40. Nomes sempre em minúsculas, exatamente assim. O manual GeoRisk sobrepõe moderado (1,00–1,80) e alto (1,60–2,60); o protótipo adota o corte em **1,80** até a decisão 2 (ver Decisões em aberto). |
| RN-02 | **Alerta**: município está "em alerta" quando o índice é ≥ 1,00 (classe moderado ou acima). |
| RN-03 | **Risco nunca só por cor**: toda indicação de classe traz cor + ícone de forma própria + nome (ou valor). Ícones: 1–2 círculo com ✓, 3 olho, 4 triângulo !, 5 triângulo !!, 6 octógono !, 7 octógono ×. |
| RN-04 | **Hachura** no mapa para classe ≥ 4, mais densa quanto maior a classe; classes 6 e 7 com hachura cruzada. |
| RN-05 | **Cores de risco** só vêm da escala de classes (`risk-1…7` na paleta GeoRisk ou `acc-1…7` na paleta Acessível). Nenhuma outra cor representa risco. As cores de risco não mudam com o tema. |
| RN-06 | **Linguagem condicional**: o VIGIA nunca afirma que haverá deslizamento ou alerta oficial; usa "poderá entrar em estado de alerta". Toda tela com índice exibe o aviso de RF-GLB-10. |
| RN-07 | **Formato numérico** (PT e ES): vírgula decimal; índice com 2 casas (`1,34`); mm com 1 casa (`72,0 mm`); razão com 2 casas e "×"; coordenadas com 4 casas e hemisfério (`27,0007° S, 49,5212° O`); unidade sempre junto do número. |
| RN-08 | **Previsões**: D0 é o dia-alvo ("hoje"); D1–D3 são estimativas e aparecem sempre identificadas como "Previsão · data — valores estimados". |
| RN-09 | **Cálculo da simulação**: parte da condição atual do município. Na implementação, usar a mesma equação do subíndice GeoRisk com a chuva informada no lugar da prevista: índice simulado = (EfR + chuva informada) ÷ Limiar. No protótipo vale a fórmula ilustrativa: chuva efetiva simulada = chuva efetiva atual × decaimento(período) + mm informados, com decaimento 0,85 (24 h), 0,72 (48 h), 0,61 (72 h); índice simulado = fator local × chuva efetiva simulada ÷ limiar, onde fator local = índice atual ÷ (chuva efetiva atual ÷ limiar). Sem chuva regional, só o município escolhido muda; com chuva regional, os 6 recebem a mesma chuva. |
| RN-10 | **Aviso da simulação**: índice simulado ≥ 2,60 → nível crítico ("poderá entrar em estado de alerta máximo… ligue 199"); ≥ 1,00 e atual < 1,00 → "poderá entrar em alerta"; ≥ 1,00 e atual ≥ 1,00 → "continuaria em alerta"; < 1,00 → "Abaixo do nível de alerta". |
| RN-11 | **Simulação é um ambiente fechado**: não altera índices reais, não fica salva, não dispara aviso no Telegram e não aparece em outras telas. |
| RN-12 | **Tendência**: variação diária > +0,005 é "subindo", < −0,005 é "descendo", senão "estável". |
| RN-13 | **Escalas fixas**: pluviômetro 0–150 mm (para comparar municípios); gráfico de evolução com eixo até 2,00, ampliado automaticamente se algum valor passar disso; escala da simulação 0–4. |
| RN-14 | **Chuva nas últimas 24 h**: acumulado de 24 h > 1 mm mostra "choveu nas últimas 24h"; caso contrário, "sem chuva agora". |
| RN-15 | **Contatos**: só dados verificados com a prefeitura vão ao ar em produção. Contatos "a confirmar" aparecem apenas no protótipo. Sem telefone, o cartão oferece o site da prefeitura. O 199 fica em destaque no topo, fora dos cartões municipais. |
| RN-16 | **Telegram**: o site só encaminha para o bot; todas as escolhas (municípios, cancelamento) acontecem dentro do bot. Nenhum dado pessoal é pedido no site. |
| RN-17 | **Aviso do bot**: enviado quando o município escolhido atinge índice ≥ 1,00 (classe moderado ou acima); não se repete enquanto o município permanecer na mesma classe, e é enviado de novo se ele subir de classe. |
| RN-18 | **Monitoramento SC**: o mapa oficial só é incorporado com autorização da SDC-SC e se o site permitir (`X-Frame-Options`/`frame-ancestors`); o crédito da fonte e o link "Abrir em nova aba" ficam sempre visíveis. |
| RN-19 | **Menu**: Contatos é sempre o último item. |
| RN-20 | **Botão primário**: fundo laranja (`accent`) com texto escuro (`on-accent`). O laranja marca só o que está ativo ou a ação principal, nunca decoração. |
| RN-21 | **Dia-alvo e horário da atualização** sempre visíveis no cabeçalho. |
| RN-22 | **Município não monitorado** aparece em cinza (`risk-nm` / contexto), sem índice. |

### Especificação das Telas

Estrutura comum: **rail lateral** (64 px) + **cabeçalho** (60 px) + **corpo**. No celular (< 900 px), barra inferior no lugar do rail.

#### Elementos globais

**Cabeçalho** (fundo azul-marinho `nav-900`), da esquerda para a direita:
1. Marca: alvo laranja + "VIGIA" / "DESLIZAMENTOS".
2. Região: rótulo "REGIÃO" + "Vale Norte — Alto Vale do Itajaí, SC".
3. Botão "Alertas no Telegram" (disco azul Telegram).
4. Seletor de idioma: globo + PT | ES.
5. Botão de Acessibilidade (ícone de pessoa).
6. Status: ponto verde + "dia-alvo 22/09/2026 · atualizado 17:14".

**Rail**: hambúrguer; 7 itens (ícones mapa, nuvem com chuva, gráfico, antena, estação, livro, telefone); rodapé com Acessibilidade.

**Janela do Telegram**: coluna principal (título, texto, 3 linhas com ícone, botão "Abrir no Telegram", "Ou procure @VigiaDeslizamentosBot" + copiar) e coluna "Como aparece no Telegram" (prévia do chat com teclado de municípios + "Todos").

**Painel de Acessibilidade**: 3 grupos de botões segmentados: Idioma (Português, Español), Tema (Automático, Claro, Escuro, Alto contraste) com nota "Alto contraste: melhor leitura sob sol forte. Escuro: para ambientes com pouca luz.", Cores do mapa (GeoRisk, Acessível (daltonismo)) com nota "Em qualquer opção, cada classe também tem ícone, nome e hachura no mapa."

#### Monitoramento — rota `/`

- **Objetivo:** ver o risco de hoje e dos próximos 3 dias e detalhar um município.
- **Layout:** mapa ocupando a largura + painel do município à direita (330 px). No celular, o painel vai para baixo do mapa.
- **Sobre o mapa:** zoom (alto-esquerda); cartão Previsões ao lado; camadas Satélite/Neutro/Ruas/Relevo (alto-direita); faixa "Previsão…" (quando D1–D3); legenda recolhível e lupa (baixo-esquerda); resumo "N de 6 em alerta" (baixo-direita); atribuição Leaflet.
- **Painel:** "MUNICÍPIO SELECIONADO" → nome → pílula "Em alerta / Sem alerta · classe X" → índice grande com selo → subtítulo "índice de risco · classe" → variáveis (chuva efetiva antecedente, limiar crítico, razão chuva/limiar, membros de ensemble) → botões Compartilhar (primário) e Simular chuva → botão Telegram do município → aviso de apoio à decisão.
- **Estados:** hoje × previsão; município em alerta × sem alerta; legenda recolhida × aberta × fixada; busca fechada × aberta × sem resultado; aviso "Link copiado" temporário.
- **Dados:** índice D0–D3 por município, chuva efetiva, limiar, membros de ensemble, polígonos IBGE, dia-alvo e hora.

#### Simulação — rota `/simulacao`

- **Objetivo:** "E se chover…?" — ver como o índice reagiria a uma chuva informada.
- **Layout:** formulário à esquerda + mapa à direita.
- **Formulário:** rótulo "SIMULAÇÃO DE CENÁRIO", título "E se chover…?", texto "Parte das condições de agora (data, hora)…"; Município; Período; Chuva esperada (slider + número + "mm") e atalhos; opção de chuva regional; botões Simular (primário) e Restaurar; área de resultado; nota "Cálculo ilustrativo…".
- **Mapa:** aviso do resultado no topo; alternância Agora | Simulado (alto-direita); cartão "Condição atual / Cenário simulado · N de 6 em alerta" (baixo-esquerda); legenda; zoom.
- **Estados:** sem simulação (condição atual); simulado com aviso ok / warn / crit; chuva regional; visão Agora × Simulado.
- **Dados:** índice e chuva efetiva atuais, limiar e fator local de cada município.

#### Dados da análise — rota `/dados`

- **Objetivo:** mostrar como a região chegou ao índice de hoje.
- **Layout:** título "Como a região chegou até aqui" + seletor 7/5/15 dias → faixa de 4 indicadores → grade de 2 colunas (gráfico de evolução | chuva acumulada) → tabela por município.
- **Estados:** município em destaque (padrão Ibirama); linha da tabela destacada; etiqueta de chuva nas últimas 24 h.
- **Dados:** série diária do índice (7/5/15 dias), acumulados 24/48/72/96 h, limiar, chuva efetiva.

#### Monitoramento SC — rota `/monitoramento-sc`

- **Objetivo:** dar acesso ao mapa oficial da Defesa Civil de SC dentro do VIGIA.
- **Layout:** cartão de introdução com "Abrir em nova aba" → moldura do iframe (barra com título e URL, área do mapa, rodapé de fonte).
- **Estados:** iframe carregado × bloqueado (plano B com "Abrir mapa oficial").
- **Só no protótipo:** a checklist "Antes de integrar (para o time)" e o seletor "Pré-visualizar estado" são material para a equipe e **não** vão para produção.

#### Estações — rota `/estacoes`

- **Objetivo:** mostrar onde ficam as estações que captam chuva e nível de rio.
- **Layout:** mapa (municípios em branco com nome) + lista lateral à direita com texto de introdução e nota de fonte.
- **Estados:** nenhuma estação selecionada × estação selecionada (pin laranja + balão + item da lista destacado).
- **Dados:** para cada estação: id, nome, tipo (`pluv`, `regua`, `met`), município, fonte, lat, lon.

#### Cartilha — rota `/cartilha`

- **Objetivo:** ensinar a reconhecer sinais de perigo e agir, com pouco texto.
- **Layout:** faixa de topo azul com título e botão 199 → navegação por âncoras fixa → 4 seções numeradas → banner Telegram → fontes.
- **Estados:** cartão virado × não virado; aba Antes/Durante/Depois; itens da mochila marcados e barra de progresso.
- **Conteúdo fixo:**
  - Antes: plante grama na encosta; leve a água da chuva para longe; receba alertas (SMS 40199 ou Telegram); deixe a mochila pronta.
  - Durante: acompanhe os avisos; viu sinais? saia já; não atravesse lama correndo; ligue 199.
  - Depois: espere a Defesa Civil liberar; peça vistoria antes de voltar; fique longe da área atingida; fotografe os danos.

#### Contatos — rota `/contatos`

- **Objetivo:** reunir emergência e Defesa Civil de cada município.
- **Layout:** título "Defesa Civil e emergência" + "Em perigo, ligue 199 de qualquer lugar. Os números funcionam 24 horas." → 4 cartões de emergência → banner Telegram → filtro "Seu município" → grade de cartões municipais → nota sobre "Como chegar" e contatos a confirmar.
- **Estados:** filtro vazio (todos) × um município (demais esmaecidos); cartão verificado × a confirmar; com telefone × sem telefone.
- **Dados:** por município: nome, verificado, responsável, telefone, e-mail, endereço, site.

### Rastreabilidade

#### Módulo RADIAN × Tela

| Módulo RADIAN | MON | SIM | DAD | SC | EST | CAR | CON | Global/TG |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Gestão da Interface do Usuário | ● | ● | ● | ● | ● | ● | ● | ● |
| Usuários (Treinamento & Capacitação) | | ● | | | | ● | | |
| Análise e Tomada de Decisão | ● | ● | ● | | | ● | | |
| Supervisão da Execução (Alertas, Comunicação) | ● | | | | | ● | ● | ● |
| Acesso e Gerenciamento de Dados | ● | ● | ● | | ● | | ● | |
| Acesso e Gerenciamento de Conhecimento | ● | | | | | ● | | ● |
| LGPD e Privacidade | | | | | | | | ● |
| Segurança | ● | ● | ● | ● | ● | ● | ● | ● |
| Interoperabilidade / Coleta e Ingestão | ● | | ● | ● | ● | | ● | ● |
| Ecossistema (sistemas externos) | ● | | ● | ● | ● | ● | ● | ● |

#### Objetivo × Requisitos

| Objetivo | Requisitos principais |
|---|---|
| OBJ-01 Risco de hoje e previsão | RF-MON-01…10, RF-DAD-01…06, RF-EXT-01…05, RN-01, RN-02, RN-08 |
| OBJ-02 Simulação | RF-SIM-01…10, RN-09, RN-10, RN-11 |
| OBJ-03 Levar a agir | RF-CAR-01…07, RF-CON-01…06 |
| OBJ-04 Avisos no celular | RF-GLB-07, RF-MON-13, RF-TG-01…05, RN-16, RN-17 |
| OBJ-05 Acessibilidade | RF-GLB-04…09, RNF-01…08, RN-03, RN-04 |
| OBJ-06 Não substituir canais oficiais | RF-GLB-10, RF-SC-01…03, RN-06, RN-18 |

## Tecnologias

- **Frontend:** Astro + React
- **Mapas:** Leaflet + OpenStreetMap
- **Dados geográficos:** GeoJSON (malhas municipais do IBGE)
- **Backend:** Python
- **API:** FastAPI
- **Cálculo:** pandas / NumPy
- **Agendamento:** APScheduler (ou cron no host)
- **Bot:** python-telegram-bot
- **Banco de dados:** PostgreSQL (ou SQLite na fase inicial)
- **Hospedagem do frontend:** GitHub Pages
- **Hospedagem do backend:** *a definir* — ver [Decisões em aberto](#decisões-em-aberto)
- **Arquitetura de referência:** RADIAN
- **Ícones:** Lucide
- **Tipografia:** Archivo (interface) e IBM Plex Mono (dados)
- **Idiomas:** Português e Español (rotas `/pt` e `/es` do Astro ou i18next)
- **Acessibilidade:** verificação com axe-core antes de cada publicação

> **Sobre a escolha do backend:** o GitHub Pages serve apenas conteúdo estático, e o bot com inscrição por usuário exige um processo em execução contínua e um banco de inscritos. Isso torna necessário um backend próprio, hospedado fora do GitHub Pages. Python foi escolhido por concentrar as bibliotecas adequadas ao tipo de processamento da metodologia (séries horárias, decaimento exponencial, agregação de ensemble) e por ter a biblioteca de bot mais madura para o caso de uso.

### Rotas

| Tela | Rota |
|---|---|
| Monitoramento | `/` |
| Simulação | `/simulacao` (aceita município de origem) |
| Dados da análise | `/dados` |
| Monitoramento SC | `/monitoramento-sc` |
| Estações | `/estacoes` |
| Cartilha | `/cartilha` |
| Contatos | `/contatos` |

### Componentes (protótipo → implementação)

| Protótipo | Implementação |
|---|---|
| `V.rail` / `V.header` (`lib.js`) | `RailLateral.tsx` (barra inferior < 900 px) e `Cabecalho.tsx` com PT/ES, Telegram e Acessibilidade |
| `V.mapa` (SVG) | `Mapa.tsx` com react-leaflet + GeoJSON IBGE; estilo por classe, hachura (`fillPattern`) para classe ≥ 4, polígonos focáveis (`keyboard: true`) com `aria-label` |
| `V.sw(n)` | `SeloClasse.tsx`: cor + ícone de forma + nome |
| `W.legenda` | controle Leaflet `LegendaRecolhivel` |
| `W.busca` | `BuscaMunicipio` (combobox acessível, `aria-activedescendant`, busca sem acento) |
| `W.previsoes` | `SeletorPrevisao` D0–D3 com play |
| `W.pluviometro`, `W.evolucao` | `Pluviometro`, `GraficoEvolucao` (SVG próprio ou lib leve) |
| `W.modal` | diálogo acessível (pode ser `<dialog>` nativo) |
| `W.telegram`, `W.tgBanner` | `CadastroTelegram` (mensagem + botão `https://t.me/<bot>?start=<slug>`) |
| `W.acess` | `PainelAcessibilidade` (idioma, tema, paleta; `localStorage`) |
| `W.aviso` | `AvisoSimulacao` (ok / warn / crit) |
| `pages/est.js` | `L.marker` por estação (lat/lon) |
| `pages/cont.js` | `CartaoContato` por município |

### Design system

Definido no protótipo navegável (pasta `vigia-prototipo/`, ainda fora deste repositório):

- **Tokens** em `vigia-prototipo/design-system/tokens.json`, temas `light`, `dark` e `contraste`. Implementar como CSS custom properties com os mesmos nomes (`--nav-900`, `--accent`, `--on-accent`, `--accent-ink`, `--risk-1…7`, `--risk-icon-1…7`, `--acc-1…7`, `--acc-icon-1…7`, `--rain`, `--rain-track`…). Troca de tema com `[data-theme="dark"|"contraste"]`; sem atributo, segue `prefers-color-scheme`.
- **Guia visual** (tom, cores, tipografia, layout, acessibilidade, iconografia): `design-system/README.md`.
- **Regras por componente e tela:** `design-system/components/<Nome>/README.md`.

## Estrutura do repositório

```
vigia-deslizamentos/
├── backend/
│   ├── app/
│   │   ├── coleta/          # Clientes das APIs de precipitação
│   │   ├── calculo/         # Chuva efetiva, subíndices, índice de risco
│   │   ├── classificacao/   # Classes de risco e probabilidades
│   │   ├── bot/             # Bot do Telegram
│   │   ├── api/             # Endpoints FastAPI
│   │   └── modelos/         # Modelos de dados e persistência
│   ├── config/
│   │   └── municipios.json  # Limiar, meia-vida e pontos de cálculo por município
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/      # Componentes de interface (React)
│   │   ├── layouts/         # Layouts Astro
│   │   ├── pages/           # Páginas do site
│   │   └── data/            # GeoJSON dos municípios e camadas estáticas
│   └── public/
└── docs/                    # Metodologia, fontes de dados e decisões de projeto
```

> Estrutura sujeita a ajustes conforme o projeto evolui.

## Roteiro de desenvolvimento

1. Definição dos requisitos funcionais e das regras de negócio;
2. Levantamento dos parâmetros por município (código IBGE, limiar crítico, pontos de cálculo);
3. Integração das fontes de precipitação observada e prevista;
4. Implementação do cálculo do índice de risco conforme a metodologia GeoRisk;
5. Persistência e exposição dos resultados via API;
6. Implementação do mapa e dos painéis de visualização;
7. Implementação do bot do Telegram com inscrição e disparo;
8. Testes e verificação dos cálculos contra os resultados públicos do GeoRisk para os mesmos municípios e datas;
9. Publicação da versão inicial.

## Decisões em aberto

Pontos que precisam ser resolvidos antes ou durante a definição dos requisitos funcionais:

| # | Decisão | Impacto |
|---|---------|---------|
| 1 | **Origem dos limiares críticos dos seis municípios.** O manual técnico descreve a metodologia, mas não fornece os valores por município — eles vêm de pesquisas do Cemaden, literatura ou Defesas Civis, e são atualizados periodicamente. Verificar se os municípios são monitorados pelo Cemaden e se o limiar é consultável na interface do GeoRisk; caso contrário, definir valor de referência documentado. | Alto — é o parâmetro central da fórmula |
| 2 | **Corte entre as classes moderado e alto** (o manual apresenta 1,80 e 1,60 em sobreposição). | Médio — afeta classificação e gatilho de notificação |
| 3 | **Hospedagem do backend** (serviço em nuvem de camada gratuita, VM da universidade ou outra opção). | Alto — bloqueia o deploy do bot |
| 4 | **Frequência de execução do pipeline.** O GeoRisk recalcula a cada nova rodada de previsão numérica (a partir de 6 em 6 horas). Definir o intervalo do VIGIA conforme os limites de uso das APIs. | Médio |
| 5 | **Modelos de previsão a utilizar e pesos atribuídos**, já que não haverá calibração. | Médio — afeta a comparabilidade com o GeoRisk |
| 6 | **Modo de operação do bot** (long polling ou webhook), que depende da hospedagem escolhida. | Médio |
| 7 | **Viabilidade da camada sub-municipal**, a confirmar no levantamento de dados do CPRM. | Baixo — funcionalidade condicional |
| 8 | **Política de dados dos inscritos do Telegram** (o que é armazenado, por quanto tempo, como é excluído). | Médio — necessário para as regras de negócio |
| 9 | **Cor da classe extremamente alto:** app atual `#a349a3` × GeoRisk `#713371`. | Baixo |
| 10 | **Paleta Acessível** (daltonismo, `acc-1…7`) a validar com o time. | Baixo |
| 11 | **Incorporação do mapa oficial da Defesa Civil de SC** via iframe: confirmar se o site permite (`X-Frame-Options`/`frame-ancestors`) e pedir autorização à SDC-SC. Sem isso, a tela mostra só o link. | Médio |
| 12 | **Contatos das seis Defesas Civis municipais** (coordenador, telefone, endereço) a levantar e verificar; só Ibirama está verificado. | Médio — nada vai ao ar "a confirmar" |
| 13 | **Estações exibidas na tela Estações:** levantar as reais com coordenadas e mostrar apenas fontes efetivamente usadas (Cemaden fora da v1; INMET integrado). | Baixo |
| 14 | **Funcionalidades sem tela no protótipo** (RF-EXT-01…05: probabilidades complementares, limiar e fonte, camada CPRM, dados brutos, histórico de ocorrências) precisam ser desenhadas. | Médio |

## Aviso importante

O VIGIA Deslizamentos é um **projeto acadêmico** e um **sistema de apoio à decisão**. Seus resultados:

- **não constituem alerta oficial** e não substituem os alertas e boletins emitidos pelo Cemaden/MCTI ou pelas Defesas Civis municipais e estadual;
- são gerados por uma implementação simplificada e **não calibrada** da metodologia do GeoRisk, com limitações declaradas neste documento;
- indicam condições regionais favoráveis à ocorrência de deslizamentos, **não a localização exata** de eventos.

Em situação de risco, as orientações da Defesa Civil prevalecem.

## Como contribuir

Este é um projeto acadêmico desenvolvido no âmbito do Projeto Integrador II. Sugestões, correções e contribuições da comunidade são bem-vindas por meio de *issues* e *pull requests* neste repositório.

## Licença

Projeto de caráter acadêmico. Uso, licenciamento e reaproveitamento dos dados serão detalhados conforme o projeto avança.

## Equipe

Projeto desenvolvido por Guilherme Rode e Kaique de Oliveira.
