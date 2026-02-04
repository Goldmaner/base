# Central de Certidões - Instalação e Configuração

## 📋 Visão Geral

Sistema para gerenciamento centralizado de certidões por OSC, com upload de arquivos, controle de vencimento e geração automática de pastas para OSCs ativas.

## 🚀 Instalação

### 1. Criar a Tabela no Banco de Dados

Execute o script SQL para criar a tabela e índices:

```bash
psql -U seu_usuario -d seu_banco -f scripts/criar_tabela_certidoes.sql
```

Ou copie e execute o conteúdo do arquivo no pgAdmin/DBeaver.

### 2. Configurar Permissões de Acesso

Execute o script para adicionar o módulo 'certidoes' aos usuários:

```bash
psql -U seu_usuario -d seu_banco -f scripts/adicionar_acesso_certidoes.sql
```

**Opções disponíveis no script:**
- **OPÇÃO 1**: Adicionar para todos os Agentes Públicos (recomendado)
- **OPÇÃO 2**: Adicionar para um usuário específico
- **OPÇÃO 3**: Adicionar para todos os usuários

Escolha a opção adequada e execute apenas as linhas correspondentes.

### 3. Criar Diretório de Upload

Certifique-se de que a pasta `modelos/Certidoes` existe e tem permissões de escrita:

```bash
# No Windows (PowerShell)
New-Item -ItemType Directory -Force -Path "modelos\Certidoes"

# No Linux/Mac
mkdir -p modelos/Certidoes
chmod 755 modelos/Certidoes
```

### 4. Reiniciar o Servidor

```bash
python run_prod.py
```

## 🎯 Como Usar

### 1. Acessar a Central

- Faça login no sistema
- Na tela inicial, clique em **"Central de Certidões"** (botão roxo na seção Geral)

### 2. Gerar Pastas de OSCs Ativas

- Clique no botão **"Gerar Pastas de OSCs Ativas"**
- **NOVO**: Um relatório detalhado será exibido mostrando:
  - Lista de todas as OSCs que serão afetadas
  - Quantidade de termos e parcelas por OSC
  - Detalhamento de cada parcela (termo, mês/ano, vigência, tipo, valor)
  - **Status de cada pasta**: ✅ "Pasta Existe" ou 🆕 "Pasta Nova"
  - Resumo geral com totais e quantidade de pastas novas vs existentes
- Revise o relatório cuidadosamente
- Clique em **"Confirmar e Gerar Pastas"** para proceder
- **O sistema é inteligente**:
  - ✅ Verifica quais pastas já existem
  - ✅ Cria APENAS pastas novas (OSCs que ainda não têm pasta)
  - ✅ Mantém pastas existentes intactas (não recria, não sobrescreve)
  - ✅ Perfeito para executar periodicamente ao adicionar novas parcelas
- O sistema criará automaticamente pastas para todas as OSCs que possuem:
  - Parcelas com vigência a partir de 01/01/2026
  - Tipo: Programada ou Projetada
  - Status: Não Pago

**💡 Dica de Uso:**
Execute esta função sempre que adicionar novas parcelas futuras no sistema. Você pode rodar quantas vezes quiser - apenas as OSCs novas terão pastas criadas, as existentes são preservadas.

### 3. Encartar uma Certidão

- Clique em **"Encartar Nova Certidão"**
- Preencha os dados:
  - Nome da OSC
  - CNPJ
  - Nome da Certidão (ex: Certidão Negativa de Débitos Federais)
  - Emissor (ex: Receita Federal)
  - Data de Vencimento
  - Arquivo (PDF, JPG, PNG ou ZIP)
  - Observações (opcional)
- Clique em **"Encartar Certidão"**

### 4. Visualizar Certidões

- As certidões aparecem agrupadas por OSC
- Clique no card da OSC para expandir e ver as certidões
- **Código de cores:**
  - 🟢 **Verde**: Certidão válida
  - 🟡 **Amarelo**: Vence em até 30 dias
  - 🔴 **Vermelho**: Certidão vencida

### 5. Gerenciar Certidões

- **Baixar**: Clique no ícone 📥 para fazer download
- **Editar**: Clique no ícone ✏️ para atualizar dados (não altera o arquivo)
- **Excluir**: Clique no ícone 🗑️ para remover (exclui arquivo e registro)

### 6. Filtrar Certidões

Use os filtros no topo da página:
- **Filtrar por OSC**: Digite parte do nome da OSC
- **Filtrar por CNPJ**: Digite o CNPJ (com ou sem formatação)
- Clique em **"Filtrar"** para aplicar
- Clique em **"Limpar"** para remover filtros

## 📊 Estrutura de Dados

### Tabela: `public.certidoes`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | SERIAL | ID único da certidão |
| osc | TEXT | Nome da OSC |
| cnpj | VARCHAR(20) | CNPJ da OSC |
| certidao_nome | VARCHAR(120) | Nome/tipo da certidão |
| certidao_emissor | VARCHAR(100) | Órgão emissor |
| certidao_vencimento | DATE | Data de vencimento |
| certidao_path | TEXT | Caminho do arquivo |
| certidao_arquivo_nome | VARCHAR(255) | Nome original |
| certidao_arquivo_size | BIGINT | Tamanho em bytes |
| certidao_status | VARCHAR(30) | Status (válida/vencida/cancelada) |
| observacoes | TEXT | Observações |
| encartado_por | VARCHAR(80) | Usuário que fez upload |
| created_at | TIMESTAMP | Data de criação |
| updated_at | TIMESTAMP | Última atualização |

### Estrutura de Arquivos

```
modelos/Certidoes/
├── Nome_OSC_1/
│   ├── 20260204_140530_certidao.pdf
│   └── 20260204_141045_certidao2.pdf
├── Nome_OSC_2/
│   └── 20260204_142100_certidao.pdf
└── ...
```

## 🔐 Gerenciar Permissões

### Via Interface Web

1. Acesse o sistema como **Agente Público**
2. Clique em **"Gerenciar Usuários"**
3. Clique em **"Editar"** no usuário desejado
4. Na seção **"Geral"**, marque o checkbox **"Central de Certidões"**
5. Clique em **"Salvar Alterações"**

### Via SQL

```sql
-- Ver usuário específico
SELECT email, acessos FROM gestao_pessoas.usuarios WHERE email = 'usuario@exemplo.com';

-- Adicionar acesso
UPDATE gestao_pessoas.usuarios
SET acessos = CASE 
    WHEN acessos IS NULL OR acessos = '' THEN 'certidoes'
    WHEN acessos NOT LIKE '%certidoes%' THEN acessos || ';certidoes'
    ELSE acessos
END
WHERE email = 'usuario@exemplo.com';

-- Remover acesso
UPDATE gestao_pessoas.usuarios
SET acessos = REPLACE(REPLACE(REPLACE(acessos, ';certidoes', ''), 'certidoes;', ''), 'certidoes', '')
WHERE email = 'usuario@exemplo.com';
```

## 🔧 Solução de Problemas

### Erro: "Você não tem permissão para acessar o módulo: certidoes"

**Solução:**
1. Verifique se o usuário tem o acesso configurado:
   ```sql
   SELECT email, tipo_usuario, acessos FROM gestao_pessoas.usuarios WHERE email = 'seu_email';
   ```
2. Se não tiver, execute:
   ```sql
   UPDATE gestao_pessoas.usuarios
   SET acessos = CASE 
       WHEN acessos IS NULL OR acessos = '' THEN 'certidoes'
       ELSE acessos || ';certidoes'
   END
   WHERE email = 'seu_email';
   ```
3. Faça logout e login novamente para atualizar a sessão

### Erro ao fazer upload de arquivo

**Solução:**
1. Verifique se a pasta `modelos/Certidoes` existe
2. Verifique permissões de escrita na pasta
3. Verifique se o arquivo tem uma das extensões permitidas: PDF, JPG, PNG, ZIP
4. Verifique logs do servidor para mais detalhes

### Pastas não são geradas

**Solução:**
1. Verifique se existem OSCs com parcelas futuras não pagas:
   ```sql
   SELECT DISTINCT p.osc, p.cnpj, COUNT(ul.id) as total_parcelas
   FROM gestao_financeira.ultra_liquidacoes ul
   INNER JOIN public.parcerias p ON ul.numero_termo = p.numero_termo
   WHERE ul.vigencia_inicial >= '2026-01-01'
     AND ul.parcela_tipo IN ('Programada', 'Projetada')
     AND ul.parcela_status = 'Não Pago'
   GROUP BY p.osc, p.cnpj;
   ```
2. Verifique permissões de escrita na pasta `modelos/Certidoes`

## ❓ Perguntas Frequentes (FAQ)

### 1. Posso executar "Gerar Pastas" múltiplas vezes?

✅ **SIM!** Pode executar quantas vezes quiser. O sistema:
- Verifica quais pastas já existem
- Cria APENAS as novas
- Mantém as existentes intactas
- É seguro executar periodicamente

### 2. O que acontece se eu adicionar parcelas de uma OSC que já tem pasta?

✅ **Nada de errado!** Quando você executar "Gerar Pastas" novamente:
- A pasta existente será detectada
- Não será recriada ou sobrescrita
- Aparecerá no relatório como "Pasta Existe"
- Seus arquivos dentro da pasta ficam seguros

### 3. Como funciona quando adiciono uma OSC nova com parcelas futuras?

✅ **Automático!** Basta:
1. Adicionar as parcelas da OSC nova no sistema
2. Clicar em "Gerar Pastas de OSCs Ativas"
3. O relatório mostrará a nova OSC com badge "Pasta Nova"
4. Confirmar e a pasta será criada

### 4. Posso adicionar certidões de OSCs que não têm pasta gerada ainda?

✅ **SIM!** Você pode:
- Adicionar certidões manualmente para qualquer OSC
- O sistema cria a pasta da OSC automaticamente no upload
- Não precisa gerar as pastas antes de adicionar certidões

### 5. Qual a diferença entre gerar pastas e adicionar certidões?

**Gerar Pastas:**
- Cria a estrutura de pastas vazias
- Baseado em parcelas futuras do sistema
- Prepara as pastas para receber certidões
- Útil para organização prévia

**Adicionar Certidões:**
- Faz upload de arquivo + cadastra no sistema
- Cria a pasta da OSC se não existir
- Associa o arquivo à OSC

### 6. Como sei quais OSCs precisam de certidões?

Use o relatório de "Gerar Pastas":
1. Clique em "Gerar Pastas de OSCs Ativas"
2. Veja a lista completa de OSCs com parcelas futuras
3. Verifique quais têm certidões cadastradas
4. Priorize as que não têm documentos

### 7. O que acontece se eu excluir uma pasta manualmente do servidor?

- A pasta será recriada na próxima execução de "Gerar Pastas"
- Aparecerá como "Pasta Nova" no relatório
- Arquivos dentro da pasta serão perdidos (faça backup!)

### 8. Posso mudar o nome da pasta de uma OSC?

⚠️ **Não recomendado!** Se mudar:
- O sistema criará uma nova pasta com o nome correto
- A pasta antiga ficará órfã
- Os links no banco de dados podem quebrar
- Melhor: mantenha os nomes gerados automaticamente

## 📝 Arquivos Criados

- ✅ `routes/certidoes.py` - Blueprint backend
- ✅ `templates/certidoes.html` - Interface visual
- ✅ `scripts/criar_tabela_certidoes.sql` - Schema do banco
- ✅ `scripts/adicionar_acesso_certidoes.sql` - Permissões
- ✅ `modelos/Certidoes/` - Diretório de upload

## 🎨 Cores e Design

- **Cor principal**: Roxo (#9C27B0)
- **Gradiente**: #667eea → #764ba2
- **Cards**: Expansíveis por OSC
- **Status visual**: Verde/Amarelo/Vermelho
- **Estatísticas**: Tempo real na dashboard

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique os logs do servidor Flask
2. Consulte a seção "Solução de Problemas" acima
3. Entre em contato com o administrador do sistema
