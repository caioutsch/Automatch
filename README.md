# 🚗 AutoMatch — Recomendador e Gestão Automotiva

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Google GenAI](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?logo=google-gemini&logoColor=white)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

O **AutoMatch** é uma plataforma web para auxílio na tomada de decisão na compra de veículos populares e seminovos no mercado brasileiro. O sistema conta com um formulário de diagnóstico inteligente em 7 etapas, cálculo estimado de IPVA por estado, comparador lado a lado e assistente interativo alimentado pela API do Google Gemini.

---

## ✨ Funcionalidades Principais

- **🚗 Catálogo Dinâmico:** Exibição aleatória a cada acesso com +50 veículos populares e seminovos do mercado brasileiro.
- **🎯 Diagnóstico em 7 Etapas:** Formulário de perfil que analisa orçamento granular, câmbio, ano, prioridades e estimativa de IPVA por estado, recomendando os top 4 matches.
- **⚖️ Comparador Lado a Lado:** Comparação em tempo real de especificações técnicas, motorização e médias de consumo urbano/rodoviário.
- **🤖 AutoMatch AI:** Assistente virtual inteligente integrado à API do Gemini para tirar dúvidas automotivas e dar sugestões do catálogo.
- **❤️ Garagem do Usuário:** Salvamento de favoritos com persistência no SQLite.
- **👤 Perfil Personalizável:** Gestão de foto de perfil, dados pessoais e veículo atual da garagem.

---

## 🛠️ Tecnologias Utilizadas

- **Back-end:** Python 3, Flask, SQLite3
- **Front-end:** HTML5, CSS3 moderno (Flexbox/Grid), JavaScript (ES6+), Phosphor Icons
- **Inteligência Artificial:** `google-genai` SDK (Modelo Gemini 2.5 Flash)
- **Gerenciamento de Ambiente:** `python-dotenv`

---

## 🚀 Como Executar o Projeto Localmente

### Pré-requisitos
- Python 3.10 ou superior instalado
- Chave de API do Google Gemini (`GEMINI_API_KEY`)

### Passo a Passo

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/SEU-USUARIO/automatch.git](https://github.com/SEU-USUARIO/automatch.git)
   cd automatch