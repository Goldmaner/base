"""
Script para adicionar colunas de configuração de campos dinâmicos
à tabela categoricas.c_alt_tipo

Executa o SQL que adiciona alt_campo_tipo, alt_campo_placeholder, etc.
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_cursor

def executar_migracao():
    """Executa a migração das colunas de tipo de campo"""
    cur = get_cursor()
    
    try:
        print("=" * 60)
        print("ADICIONANDO COLUNAS DE CONFIGURAÇÃO DE CAMPOS")
        print("=" * 60)
        
        # 1. Adicionar colunas
        print("\n1. Adicionando colunas à tabela c_alt_tipo...")
        cur.execute("""
            ALTER TABLE categoricas.c_alt_tipo 
            ADD COLUMN IF NOT EXISTS alt_campo_tipo VARCHAR(50),
            ADD COLUMN IF NOT EXISTS alt_campo_placeholder TEXT,
            ADD COLUMN IF NOT EXISTS alt_campo_maxlength INTEGER,
            ADD COLUMN IF NOT EXISTS alt_campo_min INTEGER
        """)
        print("   ✓ Colunas adicionadas com sucesso")
        
        # 2. Popular dados
        print("\n2. Populando configurações de campos...")
        
        configs = [
            ('Nome do projeto', 'text', 'Digite o novo nome do projeto', None, None),
            ('Nome da organização', 'select_osc', 'Selecione a OSC', None, None),
            ('CNPJ da organização', 'text', 'XX.XXX.XXX/XXXX-XX', 18, None),
            ('Nome do responsável legal', 'text', 'Digite o nome do responsável legal', 300, None),
            ('Pessoa gestora indicada pela administração pública', 'select_pg', 'Selecione a pessoa gestora', None, None),
            ('Objeto da parceria', 'textarea', 'Descreva o objeto da parceria', None, None),
            ('Quantidade de beneficiários diretos', 'number', 'Quantidade', None, 0),
            ('Cláusulas gerais', 'textarea', 'Descreva as cláusulas gerais', None, None),
            ('Alteração de norma geral aplicável', 'textarea', 'Descreva a alteração da norma', None, None),
            ('Aumento de valor total da parceria', 'money', 'R$ 0,00', None, None),
            ('Redução de valor de valor total da parceria', 'money', 'R$ 0,00', None, None),
            ('Remanejamentos sem alteração de valor de parcela', 'text', 'SEI do orçamento', 12, None),
            ('Remanejamentos com alteração de valor de parcela', 'text', 'SEI do orçamento', 12, None),
            ('Metas e cronograma de execução', 'textarea', 'Descreva as metas e cronograma', None, None),
            ('FACC', 'text', '1511-x / 15138-9', None, None),
            ('Prorrogação de vigência', 'date', 'Nova data final', None, None),
            ('Adequação de vigência', 'date_range', 'Novas datas de início e fim', None, None),
            ('Redução de vigência da parceria', 'date', 'Nova data final', None, None),
            ('Suspensão de vigência da parceria', 'date', 'Data da suspensão', None, None),
            ('Retomada de vigência da parceria', 'date', 'Data da retomada', None, None),
            ('Justificativa do Projeto', 'textarea', 'Justificativa do projeto', None, None),
            ('Abragência geográfica', 'text', 'Abrangência geográfica do projeto', None, None),
            ('Localização do projeto', 'text', 'Localização do projeto', None, None),
            ('Faixa etária de beneficiários', 'text', 'Faixa etária dos beneficiários', None, None),
            ('Quantidade de beneficiários indiretos', 'number', 'Quantidade', None, 0),
        ]
        
        for alt_tipo, campo_tipo, placeholder, maxlength, min_val in configs:
            cur.execute("""
                UPDATE categoricas.c_alt_tipo 
                SET 
                    alt_campo_tipo = %s,
                    alt_campo_placeholder = %s,
                    alt_campo_maxlength = %s,
                    alt_campo_min = %s
                WHERE alt_tipo = %s
            """, (campo_tipo, placeholder, maxlength, min_val, alt_tipo))
            
            if cur.rowcount > 0:
                print(f"   ✓ {alt_tipo}: {campo_tipo}")
            else:
                print(f"   ⚠ {alt_tipo}: NÃO ENCONTRADO na tabela")
        
        # 3. Verificar resultado
        print("\n3. Verificando resultado...")
        cur.execute("""
            SELECT 
                alt_tipo, 
                alt_instrumento,
                alt_campo_tipo, 
                alt_campo_placeholder,
                COALESCE(alt_campo_maxlength::text, '-') as maxlength,
                COALESCE(alt_campo_min::text, '-') as min_val
            FROM categoricas.c_alt_tipo
            ORDER BY alt_tipo
        """)
        
        resultado = cur.fetchall()
        
        print(f"\n   Total de tipos configurados: {len(resultado)}")
        print("\n   Primeiros 5 registros:")
        for i, row in enumerate(resultado[:5], 1):
            print(f"   {i}. {row['alt_tipo']}")
            print(f"      Tipo: {row['alt_campo_tipo']}, Placeholder: {row['alt_campo_placeholder'][:50]}...")
        
        # 4. Commit
        cur.connection.commit()
        print("\n✓ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        
        cur.close()
        
    except Exception as e:
        print(f"\n✗ ERRO na migração: {str(e)}")
        cur.connection.rollback()
        cur.close()
        raise

if __name__ == "__main__":
    executar_migracao()
