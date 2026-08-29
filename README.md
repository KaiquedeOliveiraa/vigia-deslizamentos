# VIGIA Deslizamentos

### Sistema Integrado de Monitoramento e Apoio à Decisão para Risco de Deslizamentos

> Projeto Integrador II

## Sobre o projeto

O **VIGIA Deslizamentos** é um sistema de monitoramento e apoio à decisão voltado à identificação de condições associadas ao risco de deslizamentos de terra.

A proposta é integrar dados meteorológicos, geográficos e históricos para apresentar informações de forma simples e visual, auxiliando no acompanhamento das condições de risco por meio de um mapa interativo e indicadores de fácil leitura — tanto para gestores públicos quanto para a população em geral.

## Motivação

Deslizamentos de terra estão entre os desastres naturais mais recorrentes e letais no Brasil, especialmente em regiões de relevo acidentado combinadas com chuvas intensas e ocupação irregular de encostas. O caso mais emblemático de Santa Catarina ocorreu em novembro de 2008, quando chuvas prolongadas seguidas de temporais provocaram uma série de deslizamentos no Vale do Itajaí, resultando em mais de cem vítimas fatais e afetando dezenas de municípios da região. Episódios como esse reforçam a importância de sistemas de monitoramento capazes de antecipar cenários de risco e apoiar decisões rápidas por parte da Defesa Civil e da população.

O VIGIA Deslizamentos nasce dessa necessidade: transformar dados dispersos (chuva, relevo, histórico de ocorrências) em informação acessível e acionável.

## Objetivo

Desenvolver um sistema capaz de integrar e analisar dados relacionados à precipitação e às características das localidades, fornecendo informações que auxiliem no monitoramento e na tomada de decisão diante de possíveis situações de risco de deslizamento.

**Objetivos específicos:**

- Consolidar, em uma única plataforma, dados de precipitação, relevo e histórico de ocorrências;
- Classificar automaticamente o nível de atenção por município/região;
- Apresentar essas informações por meio de mapa interativo e painéis de indicadores;
- Estruturar o sistema de forma modular, permitindo a expansão para novas regiões sem redesenho da arquitetura.

## Área de abrangência


| Fase | Abrangência | Descrição |
|------|-------------|-----------|
| **Piloto** | Alto Vale do Itajaí (SC) | Validação da metodologia, das fontes de dados e da classificação de risco em uma região de referência, com histórico bem documentado de deslizamentos. Escopo direcionado para a região de Presidente Getúlio|

A arquitetura modular do sistema é pensada desde o início para suportar essa expansão, isolando as regras específicas de cada região (limites geográficos, fontes de dados locais, thresholds de risco) dos componentes centrais de coleta, processamento e visualização.

## Funcionamento

De forma geral, o sistema seguirá o fluxo:

**Coleta de dados → Tratamento → Análise → Classificação → Visualização**

1. **Coleta:** ingestão de dados de precipitação, relevo e ocorrências históricas a partir de APIs públicas e bases geográficas;
2. **Tratamento:** padronização, limpeza e associação dos dados aos municípios/regiões correspondentes;
3. **Análise:** cruzamento de variáveis (precipitação acumulada, declividade, histórico) segundo a metodologia de classificação;
4. **Classificação:** atribuição de níveis de atenção por localidade;
5. **Visualização:** apresentação dos resultados em mapa interativo e painéis com indicadores.

## Dados

Entre as principais categorias de dados consideradas estão:

- Precipitação histórica e acumulada;
- Previsão de precipitação;
- Dados geográficos dos municípios (limites, altitude, declividade);
- Histórico de ocorrências de deslizamentos;
- Dados relacionados às características do terreno (tipo de solo, uso e cobertura do solo).

As fontes e APIs abaixo são as candidatas iniciais, priorizando bases públicas e oficiais, de modo a facilitar a replicação da metodologia em novas regiões nas fases futuras. A confirmação de disponibilidade, limites de uso e granularidade de cada uma deve ser validada no início do desenvolvimento.

### APIs e fontes de dados candidatas

| Fonte | Tipo de dado | Observações |
|-------|--------------|-------------|
| **[INMET](https://portal.inmet.gov.br/)** — API de estações (`apitempo.inmet.gov.br`) | Precipitação, temperatura e umidade histórica e diária, por estação automática/convencional | API REST pública e gratuita; não exige chave. Cobertura nacional, boa para a série histórica de precipitação. |
| **[Open-Meteo](https://open-meteo.com/)** | Previsão de precipitação (curto prazo) e histórico climático (desde 1940) | API REST gratuita, sem chave para uso não comercial/open-source; resposta em JSON, fácil de integrar ao frontend ou à camada de coleta. Boa alternativa/complemento ao INMET para previsão. |
| **[CEMADEN](https://www.gov.br/cemaden/)** | Dados de pluviômetros automáticos e alertas de risco geológico-hidrológico | Não possui uma API REST pública simples e totalmente documentada; disponibiliza mapa interativo e dados abertos parciais. Uso pode exigir parceria formal ou extração assistida — validar durante o desenvolvimento. |
| **[IBGE — API de Localidades](https://servicodados.ibge.gov.br/api/docs/localidades)** | Malha municipal, hierarquia geográfica (estado, mesorregião, microrregião, município) | API REST pública, gratuita, estável e bem documentada. Essencial para padronizar os municípios em qualquer fase (SC ou nacional). O IBGE também expõe a **[API do SIDRA](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3)** para indicadores socioeconômicos e a **[Malhas Geográficas](https://servicodados.ibge.gov.br/api/docs/malhas)** para os polígonos em GeoJSON/TopoJSON dos municípios. |
| **[CPRM / Serviço Geológico do Brasil — GeoSGB](https://geosgb.cprm.gov.br/)** | Mapas de suscetibilidade a movimentos de massa, geologia e geomorfologia | Disponibilizado principalmente via serviços de mapa (WMS/WFS) e downloads de shapefile, não como API REST tradicional. Importante para a variável "características do terreno". |
| **[ANA — Agência Nacional de Águas (HidroWebService)](https://www.ana.gov.br/hidrowebservice)** | Dados hidrológicos (nível de rios, vazão) | Útil como variável complementar em regiões onde enchentes e deslizamentos estão associados. Requer cadastro para acesso a alguns endpoints. |
| **Defesa Civil (municipal/estadual) e [S2iD](https://s2id.mi.gov.br/)** | Histórico de ocorrências e decretos de situação de emergência/calamidade | Não é uma API tradicional (mais um portal de consulta); útil como fonte para construir a base histórica de ocorrências por município, inclusive fora de SC nas fases de expansão. |

> As APIs de precipitação (INMET/Open-Meteo) e a malha municipal (IBGE) têm cobertura nacional por natureza, o que favorece diretamente a expansão prevista na Fase 2. Já CEMADEN, CPRM e Defesa Civil variam em granularidade e formato entre estados, e serão o principal ponto de atenção ao generalizar a metodologia para fora de Santa Catarina.

## Funcionalidades previstas

- 🗺️ Mapa interativo com os municípios da área de estudo;
- 📊 Indicadores gerais de monitoramento;
- 📍 Detalhamento das condições de cada município;
- ⚠️ Classificação em níveis de atenção;
- 📱 Compartilhamento de informações de alerta;
- 🔎 Consulta dos dados utilizados na análise;
- 🌎 Seleção de região/estado, preparando o sistema para a futura expansão nacional.

## Arquitetura

O projeto utilizará a **RADIAN** como arquitetura de referência para a organização do sistema de apoio à decisão.

A arquitetura será considerada na definição dos componentes responsáveis pela aquisição, processamento, integração, análise e apresentação dos dados, garantindo que novas regiões possam ser incorporadas ao sistema sem a necessidade de reestruturação dos módulos centrais.

## Tecnologias

- **Frontend:** Astro + React
- **Mapas:** Leaflet + OpenStreetMap
- **Dados geográficos:** GeoJSON (IBGE — malhas municipais)
- **Dados meteorológicos:** INMET, Open-Meteo (ver seção [Dados](#dados))
- **Hospedagem:** GitHub Pages
- **Arquitetura:** RADIAN

## Estrutura do repositório

```
vigia-deslizamentos/
├── src/
│   ├── components/     # Componentes de interface (React)
│   ├── layouts/        # Layouts Astro
│   ├── pages/           # Páginas do site
│   ├── data/            # Dados geográficos (GeoJSON) e configurações por região
│   └── lib/             # Funções de coleta, tratamento e classificação
├── public/               # Arquivos estáticos
└── docs/                 # Documentação da metodologia e das fontes de dados
```

> Estrutura sujeita a ajustes conforme o projeto evolui.

## Roteiro de desenvolvimento

1. Definição e integração das fontes de dados;
2. Desenvolvimento da coleta e tratamento dos dados;
3. Implementação do mapa e visualização;
4. Desenvolvimento da metodologia de classificação de risco;
5. Implementação do dashboard e detalhamento;
6. Testes e validação com a região piloto (Alto Vale do Itajaí);
7. Publicação da versão inicial;
8. Avaliação da viabilidade de expansão estadual e nacional, com generalização da metodologia de classificação.

## Como contribuir

Este é um projeto acadêmico desenvolvido no âmbito do Projeto Integrador II. Sugestões, correções e contribuições da comunidade são bem-vindas por meio de *issues* e *pull requests* neste repositório.

## Licença

Projeto de caráter acadêmico. Uso, licenciamento e reaproveitamento dos dados serão detalhados conforme o projeto avança.


## Equipe

Projeto desenvolvido por Guilherme Rode e Kaique de Oliveira.
