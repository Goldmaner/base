# 🚀 Guia Rápido - Análises PC

## Inicialização (Primeira Vez)

```bash
# 1. Criar índices e validar estrutura
python scripts/inicializar_analises_pc.py

# 2. Iniciar servidor
python run_dev.py
```

## Acesso

**URL Direta:**  
http://localhost:8080/analises_pc/

**Via Menu:**  
Instruções → "Ir para o Formulário Inicial"

## Uso Básico

### 1️⃣ Configurar Análise
- Selecione o **Termo**
- Digite os **Meses** (ex: 01/2024)
- Escolha **Analista(s)**
- Clique **"Prosseguir"**

### 2️⃣ Preencher Checklist
- Marque etapas concluídas ✅
- Etapas anteriores marcam automaticamente
- Adicione recursos se necessário

### 3️⃣ Salvar
- Clique **"Salvar Avanços"** 💾
- Dados ficam salvos!

## Recursos (Opcional)

**Adicionar Recurso:**
- Clique **"+ Incluir Fase Recursal"**
- Preencha as 3 etapas
- Pode adicionar quantos precisar

**Remover Recurso:**
- Clique **"✖ Remover"** na fase

## Dicas

💡 **Retornar depois:** Selecione mesmo termo/meses para continuar  
💡 **Múltiplos analistas:** Use Ctrl+Click (Windows) ou Cmd+Click (Mac)  
💡 **Cascata:** Marcar etapa 10 marca 1-9 automaticamente  
💡 **Voltar:** Use botão "← Voltar" no topo  

## Atalhos de Teclado

- **Tab** - Navegar entre campos
- **Enter** - Confirmar seleção (dropdowns)
- **Espaço** - Marcar/desmarcar checkbox
- **Esc** - Fechar dropdown

## Troubleshooting

**Dropdown vazio?**
```bash
# Verificar dados
psql -U seu_usuario -d faf -c "SELECT COUNT(*) FROM public.parcerias;"
```

**Erro ao salvar?**
```bash
# Ver logs do servidor
# Verifique terminal onde rodou python run_dev.py
```

**Página não carrega?**
```bash
# Reiniciar servidor
Ctrl+C  # parar
python run_dev.py  # iniciar novamente
```

---

## 📞 Mais Informações

📖 Documentação completa: `docs/MODULO_ANALISES_PC.md`  
📊 Detalhes técnicos: `docs/SUMARIO_ANALISES_PC.md`  
🧪 Rodar testes: `python testes/test_analises_pc_api.py`

---

*Versão: 1.0 | Data: 07/11/2024*
