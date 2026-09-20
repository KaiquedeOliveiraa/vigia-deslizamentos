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

> **Sobre a escolha do backend:** o GitHub Pages serve apenas conteúdo estático, e o bot com inscrição por usuário exige um processo em execução contínua e um banco de inscritos. Isso torna necessário um backend próprio, hospedado fora do GitHub Pages. Python foi escolhido por concentrar as bibliotecas adequadas ao tipo de processamento da metodologia (séries horárias, decaimento exponencial, agregação de ensemble) e por ter a biblioteca de bot mais madura para o caso de uso.

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
