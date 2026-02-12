# 📊 Log de Atividades - Queries de Análise e Monitoramento

## 🔍 Queries de Análise

### 1. Dashboard Geral (Últimos 7 dias)

```sql
-- Resumo executivo de uso
SELECT 
    COUNT(*) as total_acoes,
    COUNT(DISTINCT usuario_nome) as usuarios_ativos,
    COUNT(DISTINCT acao_categoria) as categorias_usadas,
    ROUND(AVG(duracao_ms)) as duracao_media_ms,
    COUNT(*) FILTER (WHERE NOT sucesso) as total_erros,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sucesso) / COUNT(*), 2) as taxa_erro_pct
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '7 days';
```

### 2. Top 10 Usuários Mais Ativos

```sql
SELECT 
    usuario_nome,
    tipo_usuario,
    COUNT(*) as total_acoes,
    COUNT(DISTINCT DATE(created_at)) as dias_ativos,
    ROUND(AVG(duracao_ms)) as duracao_media_ms,
    COUNT(*) FILTER (WHERE acao_tipo = 'edicao') as edicoes,
    COUNT(*) FILTER (WHERE acao_tipo = 'criacao') as criacoes,
    COUNT(*) FILTER (WHERE acao_tipo = 'exclusao') as exclusoes
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY usuario_nome, tipo_usuario
ORDER BY total_acoes DESC
LIMIT 10;
```

### 3. Funcionalidades Mais Usadas

```sql
SELECT 
    acao_categoria,
    acao_tipo,
    COUNT(*) as total_usos,
    COUNT(DISTINCT usuario_nome) as usuarios_distintos,
    ROUND(AVG(duracao_ms)) as duracao_media_ms,
    MAX(duracao_ms) as duracao_maxima_ms
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY acao_categoria, acao_tipo
ORDER BY total_usos DESC
LIMIT 20;
```

### 4. Análise de Performance (Rotas Lentas)

```sql
-- Rotas com duração > 2 segundos
SELECT 
    acao_endpoint,
    acao_metodo,
    COUNT(*) as vezes_lenta,
    ROUND(AVG(duracao_ms)) as duracao_media_ms,
    MAX(duracao_ms) as duracao_maxima_ms,
    MIN(duracao_ms) as duracao_minima_ms
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '7 days'
  AND duracao_ms > 2000  -- Mais de 2 segundos
GROUP BY acao_endpoint, acao_metodo
ORDER BY duracao_media_ms DESC
LIMIT 20;
```

### 5. Taxa de Erro por Funcionalidade

```sql
SELECT 
    acao_categoria,
    COUNT(*) as total_requisicoes,
    COUNT(*) FILTER (WHERE sucesso) as sucessos,
    COUNT(*) FILTER (WHERE NOT sucesso) as erros,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sucesso) / COUNT(*), 2) as taxa_erro_pct
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY acao_categoria
HAVING COUNT(*) FILTER (WHERE NOT sucesso) > 0  -- Apenas com erros
ORDER BY taxa_erro_pct DESC;
```

### 6. Horários de Pico

```sql
-- Distribuição de uso por hora do dia
SELECT 
    EXTRACT(HOUR FROM created_at) as hora,
    COUNT(*) as total_acoes,
    COUNT(DISTINCT usuario_nome) as usuarios_ativos,
    ROUND(AVG(duracao_ms)) as duracao_media_ms
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY hora
ORDER BY hora;
```

### 7. Dias da Semana Mais Ativos

```sql
SELECT 
    TO_CHAR(created_at, 'Day') as dia_semana,
    EXTRACT(DOW FROM created_at) as dia_numero,  -- 0=domingo, 6=sábado
    COUNT(*) as total_acoes,
    COUNT(DISTINCT usuario_nome) as usuarios_ativos
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY dia_semana, dia_numero
ORDER BY dia_numero;
```

### 8. Últimas Ações de um Usuário Específico

```sql
SELECT 
    created_at,
    acao_tipo,
    acao_categoria,
    acao_endpoint,
    status_codigo,
    duracao_ms,
    sucesso
FROM gestao_pessoas.log_atividades
WHERE usuario_nome = 'NOME_DO_USUARIO'
ORDER BY created_at DESC
LIMIT 50;
```

### 9. Análise de Uso por Tipo de Usuário

```sql
SELECT 
    tipo_usuario,
    COUNT(*) as total_acoes,
    COUNT(DISTINCT usuario_nome) as total_usuarios,
    ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT usuario_nome), 2) as media_acoes_por_usuario,
    ROUND(AVG(duracao_ms)) as duracao_media_ms
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY tipo_usuario
ORDER BY total_acoes DESC;
```

### 10. Endpoints com Mais Erros

```sql
SELECT 
    acao_endpoint,
    acao_metodo,
    status_codigo,
    COUNT(*) as total_erros,
    erro_mensagem
FROM gestao_pessoas.log_atividades
WHERE NOT sucesso
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY acao_endpoint, acao_metodo, status_codigo, erro_mensagem
ORDER BY total_erros DESC
LIMIT 20;
```

---

## 🔧 Manutenção e Performance

### Tamanho da Tabela

```sql
-- Ver tamanho atual da tabela
SELECT 
    pg_size_pretty(pg_total_relation_size('gestao_pessoas.log_atividades')) as tamanho_total,
    pg_size_pretty(pg_relation_size('gestao_pessoas.log_atividades')) as tamanho_tabela,
    pg_size_pretty(pg_indexes_size('gestao_pessoas.log_atividades')) as tamanho_indices,
    (SELECT COUNT(*) FROM gestao_pessoas.log_atividades) as total_registros;
```

### Limpeza Periódica (Manter 6 meses)

```sql
-- CUIDADO: Fazer backup antes de deletar!
DELETE FROM gestao_pessoas.log_atividades
WHERE created_at < NOW() - INTERVAL '6 months';

-- Ou mover para tabela histórica
CREATE TABLE IF NOT EXISTS gestao_pessoas.log_atividades_historico (LIKE gestao_pessoas.log_atividades INCLUDING ALL);

-- Mover registros antigos
INSERT INTO gestao_pessoas.log_atividades_historico
SELECT * FROM gestao_pessoas.log_atividades
WHERE created_at < NOW() - INTERVAL '6 months';

-- Deletar após mover
DELETE FROM gestao_pessoas.log_atividades
WHERE created_at < NOW() - INTERVAL '6 months';
```

### Vacuum e Análise (Otimizar Performance)

```sql
-- Recuperar espaço após DELETEs grandes
VACUUM ANALYZE gestao_pessoas.log_atividades;

-- Reindexar se necessário (cuidado em produção - pode travar)
REINDEX TABLE gestao_pessoas.log_atividades;
```

### Monitorar Crescimento

```sql
-- Taxa de crescimento diário
SELECT 
    DATE(created_at) as data,
    COUNT(*) as total_logs,
    pg_size_pretty(
        COUNT(*) * 
        (SELECT pg_column_size(row(log_atividades.*)) 
         FROM gestao_pessoas.log_atividades 
         LIMIT 1)
    ) as tamanho_estimado
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY data DESC;
```

---

## 📈 Métricas Recomendadas

### KPIs de Uso
- Total de ações por dia/semana/mês
- Usuários ativos diários (DAU)
- Usuários ativos mensais (MAU)
- Taxa de engajamento (DAU/MAU)

### KPIs de Performance
- Tempo médio de resposta por funcionalidade
- % de requisições > 2 segundos
- Taxa de erro geral e por funcionalidade

### KPIs de Adoção
- Funcionalidades mais usadas
- Funcionalidades menos usadas (candidatas a deprecação)
- Novos usuários por período

---

## ⚠️ Alertas Recomendados

### Alerta 1: Taxa de Erro Alta

```sql
-- Se taxa de erro > 5% nas últimas 24h
SELECT 
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sucesso) / COUNT(*), 2) as taxa_erro_pct
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '24 hours'
HAVING ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sucesso) / COUNT(*), 2) > 5;
```

### Alerta 2: Performance Degradada

```sql
-- Se tempo médio > 3 segundos nas últimas 2 horas
SELECT 
    ROUND(AVG(duracao_ms)) as duracao_media_ms
FROM gestao_pessoas.log_atividades
WHERE created_at >= NOW() - INTERVAL '2 hours'
HAVING ROUND(AVG(duracao_ms)) > 3000;
```

### Alerta 3: Tabela Muito Grande

```sql
-- Se tabela > 1GB
SELECT 
    pg_size_pretty(pg_total_relation_size('gestao_pessoas.log_atividades')) as tamanho,
    pg_total_relation_size('gestao_pessoas.log_atividades') as tamanho_bytes
FROM information_schema.tables 
WHERE table_schema = 'gestao_pessoas' 
  AND table_name = 'log_atividades'
  AND pg_total_relation_size('gestao_pessoas.log_atividades') > 1073741824;  -- 1GB
```

---

## 🎯 Dicas de Otimização

1. **Particionamento por Data** (se crescer muito):
   ```sql
   -- Particionar por mês para manter performance
   CREATE TABLE gestao_pessoas.log_atividades_2026_02 
       PARTITION OF gestao_pessoas.log_atividades
       FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
   ```

2. **Índices Parciais** (para queries comuns):
   ```sql
   -- Índice apenas para erros (economiza espaço)
   CREATE INDEX idx_log_erros ON gestao_pessoas.log_atividades(created_at DESC) 
   WHERE NOT sucesso;
   
   -- Índice apenas para ações lentas
   CREATE INDEX idx_log_lentos ON gestao_pessoas.log_atividades(duracao_ms DESC) 
   WHERE duracao_ms > 2000;
   ```

3. **Agregar Estatísticas** (tabela resumida):
   ```sql
   CREATE TABLE gestao_pessoas.log_atividades_estatisticas (
       data DATE,
       acao_categoria VARCHAR(100),
       total_acoes INTEGER,
       usuarios_distintos INTEGER,
       duracao_media_ms INTEGER,
       taxa_erro_pct NUMERIC(5,2),
       PRIMARY KEY (data, acao_categoria)
   );
   
   -- Job diário para agregar
   INSERT INTO gestao_pessoas.log_atividades_estatisticas
   SELECT 
       DATE(created_at),
       acao_categoria,
       COUNT(*),
       COUNT(DISTINCT usuario_nome),
       ROUND(AVG(duracao_ms)),
       ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sucesso) / COUNT(*), 2)
   FROM gestao_pessoas.log_atividades
   WHERE DATE(created_at) = CURRENT_DATE - 1
   GROUP BY DATE(created_at), acao_categoria
   ON CONFLICT (data, acao_categoria) DO NOTHING;
   ```

---

## 📝 Notas Finais

- **Performance**: Sistema de logging é assíncrono (thread separada) e adiciona **< 1ms** de overhead
- **Retenção**: Recomendado manter 6 meses de logs (ajustar conforme necessidade)
- **Limpeza**: Configurar job semanal/mensal para deletar logs antigos
- **Monitoramento**: Revisar tamanho da tabela mensalmente
- **Backups**: Incluir tabela de logs no backup regular do banco
