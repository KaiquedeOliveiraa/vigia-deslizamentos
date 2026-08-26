# VIGIA Deslizamentos

### Sistema Integrado de Monitoramento e Apoio à Decisão para Risco de Deslizamentos

> Projeto Integrador II

## Sobre o projeto

O **VIGIA Deslizamentos** é um sistema de monitoramento e apoio à decisão voltado à identificação de condições associadas ao risco de deslizamentos.

A proposta é integrar dados meteorológicos, geográficos e históricos para apresentar informações de forma simples e visual, auxiliando no acompanhamento das condições de risco por meio de um mapa interativo e indicadores.

## Objetivo

Desenvolver um sistema capaz de integrar e analisar dados relacionados à precipitação e às características das localidades, fornecendo informações que auxiliem no monitoramento e na tomada de decisão diante de possíveis situações de risco.

## Área de abrangência

O desenvolvimento inicial terá como foco o **Alto Vale do Itajaí, em Santa Catarina**.

A estrutura será desenvolvida de forma modular, permitindo futuramente ampliar a aplicação para outras regiões de Santa Catarina e do Brasil.

## Funcionamento

De forma geral, o sistema seguirá o fluxo:

**Coleta de dados → Tratamento → Análise → Classificação → Visualização**

Os dados serão processados para gerar indicadores e níveis de atenção, apresentados ao usuário por meio de mapas e painéis.

## Dados

Entre as principais categorias de dados consideradas estão:

- Precipitação histórica e acumulada;
- Previsão de precipitação;
- Dados geográficos dos municípios;
- Histórico de ocorrências de deslizamentos;
- Dados relacionados às características do terreno.

As fontes e APIs utilizadas serão definidas e documentadas durante o desenvolvimento.

## Funcionalidades previstas

- 🗺️ Mapa interativo com os municípios da área de estudo;
- 📊 Indicadores gerais de monitoramento;
- 📍 Detalhamento das condições de cada município;
- ⚠️ Classificação em níveis de atenção;
- 📱 Compartilhamento de informações de alerta;
- 🔎 Consulta dos dados utilizados na análise.

## Arquitetura

O projeto utilizará a **RADIAN** como arquitetura de referência para a organização do sistema de apoio à decisão.

A arquitetura será considerada na definição dos componentes responsáveis pela aquisição, processamento, integração, análise e apresentação dos dados.

## Tecnologias

- **Frontend:** Astro + React
- **Mapas:** Leaflet + OpenStreetMap
- **Dados geográficos:** GeoJSON
- **Dados meteorológicos:** APIs públicas
- **Hospedagem:** GitHub Pages
- **Arquitetura:** RADIAN

## Roteiro de desenvolvimento

1. Definição e integração das fontes de dados;
2. Desenvolvimento da coleta e tratamento dos dados;
3. Implementação do mapa e visualização;
4. Desenvolvimento da metodologia de classificação de risco;
5. Implementação do dashboard e detalhamento;
6. Testes, validação e publicação.

## Status

🚧 **Em desenvolvimento**

## Equipe

Projeto desenvolvido como parte do **Projeto Integrador II**.
