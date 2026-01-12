# Implementação de SAVE para Informações Adicionais e Endereços

## Resumo
Implementada a lógica de salvamento (POST) para as tabelas `public.parcerias_infos_adicionais` e `public.parcerias_enderecos` nas rotas `nova()` e `editar()`.

## Mudanças Realizadas

### 1. Rota `/nova` (Criar Nova Parceria)
**Arquivo:** `routes/parcerias.py` - Linha ~394

#### Informações Adicionais
```python
# UPSERT em parcerias_infos_adicionais
- parceria_numero_termo (chave primária)
- parceria_responsavel_legal
- parceria_objeto  
- parceria_beneficiarios_diretos
- parceria_beneficiarios_indiretos
- parceria_justificativa_projeto
- parceria_abrangencia_projeto
- parceria_data_suspensao
- parceria_data_retomada
```

Usa `ON CONFLICT` para atualizar caso já exista registro.

#### Endereços
```python
# DELETE + INSERT em parcerias_enderecos
1. Deleta todos os endereços existentes do termo
2. Verifica se projeto_online = 'on'
3. Se NÃO online: insere múltiplos endereços
   - Loop while buscando campos com sufixos (_1, _2, _3...)
   - Para no primeiro logradouro vazio
   - Campos salvos:
     - parceria_numero_termo
     - logradouro
     - complemento
     - numero
     - cep
     - distrito
     - subprefeitura
     - regiao
     - observacao
```

### 2. Rota `/editar/<numero_termo>` (Editar Parceria)
**Arquivo:** `routes/parcerias.py` - Linha ~779

Mesma lógica da rota `/nova`:
- UPSERT em `parcerias_infos_adicionais`
- DELETE + INSERT em `parcerias_enderecos`

## Mapeamento de Campos (Form → Database)

### Informações Adicionais
| Campo HTML | Coluna Database |
|------------|-----------------|
| `responsavel_legal` | `parceria_responsavel_legal` |
| `objeto_info` | `parceria_objeto` |
| `beneficiarios_diretos` | `parceria_beneficiarios_diretos` |
| `beneficiarios_indiretos` | `parceria_beneficiarios_indiretos` |
| `justificativa` | `parceria_justificativa_projeto` |
| `abrangencia` | `parceria_abrangencia_projeto` |
| `data_suspensao` | `parceria_data_suspensao` |
| `data_retomada` | `parceria_data_retomada` |

### Endereços (Múltiplos com Sufixo)
| Campo HTML | Coluna Database |
|------------|-----------------|
| `logradouro`, `logradouro_2`, ... | `logradouro` |
| `complemento`, `complemento_2`, ... | `complemento` |
| `numero_end`, `numero_end_2`, ... | `numero` |
| `cep`, `cep_2`, ... | `cep` |
| `distrito`, `distrito_2`, ... | `distrito` |
| `subprefeitura`, `subprefeitura_2`, ... | `subprefeitura` |
| `regiao`, `regiao_2`, ... | `regiao` |
| `observacao`, `observacao_2`, ... | `observacao` |

## Checkboxes Especiais
- `projeto_online = 'on'`: Se marcado, NÃO salva endereços (projeto online não tem local físico)

## Debug/Logs
Adicionados logs:
- `[DEBUG NOVA/EDITAR] Informações adicionais salvas para {numero_termo}`
- `[DEBUG NOVA/EDITAR] {N} endereço(s) salvo(s) para {numero_termo}`
- `[ERRO] Falha ao salvar informações adicionais: {erro}`
- `[ERRO] Falha ao salvar endereços: {erro}`

## Testes Necessários
1. ✅ Criar nova parceria com infos adicionais
2. ✅ Criar nova parceria com múltiplos endereços
3. ✅ Editar parceria e alterar infos adicionais
4. ✅ Editar parceria e alterar/adicionar/remover endereços
5. ✅ Marcar "Projeto Online" e verificar que endereços NÃO são salvos
6. ✅ Verificar dados no banco após cada operação

## Arquivos Modificados
- `routes/parcerias.py` (2 rotas)
  - Linha ~394: POST `/nova`
  - Linha ~779: POST `/editar/<numero_termo>`
