"""
Script para criar tabela de Despesas de Provisão
Usada no cálculo de relatórios mistos (DP + Pessoa Gestora)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from db import get_db, get_cursor

def criar_tabela_provisoes():
    """Cria tabela c_despesas_provisao e insere dados iniciais"""
    with app.app_context():
        db = get_db()
        cur = get_cursor()
        
        print("🔄 Criando tabela categoricas.c_despesas_provisao...")
        
        # Criar tabela
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categoricas.c_despesas_provisao (
                id SERIAL PRIMARY KEY,
                despesa_provisao VARCHAR(200) NOT NULL UNIQUE,
                descricao TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
            )
        """)
        
        print("✅ Tabela criada!")
        
        # Dados iniciais
        provisoes = [
            ('Férias', 'Remuneração devida ao trabalhador durante o período de férias anuais.'),
            ('13º Salário', 'Décimo terceiro salário — parcela anual complementar calculada proporcionalmente aos meses trabalhados.'),
            ('1/3 de Férias', 'Adicional constitucional equivalente a um terço da remuneração paga juntamente com as férias.'),
            ('Indenizações', 'Valores pagos a título de indenização, incluindo rescisões e outras compensações previstas contratualmente.'),
            ('FGTS Rescisório', 'Depósito referente ao FGTS relativo à rescisão contratual (parcelas devidas no desligamento).'),
            ('Provisões', 'Categoria genérica para lançamentos contábeis de provisões trabalhistas e encargos futuros.'),
            ('Provisão', 'Lançamento contábil específico para reconhecer obrigações futuras relacionadas a pessoal ou encargos.'),
            ('Adicional de Férias', 'Valor adicional pago sobre as férias por previsão em acordo, norma interna ou convenção coletiva.'),
            ('Multa FGTS', 'Multa rescisória de 40% sobre o saldo do FGTS devida em demissão sem justa causa.')
        ]
        
        print("🔄 Inserindo despesas de provisão...")
        
        for despesa, descricao in provisoes:
            cur.execute("""
                INSERT INTO categoricas.c_despesas_provisao (despesa_provisao, descricao)
                VALUES (%s, %s)
                ON CONFLICT (despesa_provisao) DO NOTHING
            """, (despesa, descricao))
        
        db.commit()
        
        # Verificar registros inseridos
        cur.execute("SELECT COUNT(*) as total FROM categoricas.c_despesas_provisao")
        total = cur.fetchone()['total']
        
        print(f"✅ {total} despesas de provisão cadastradas!")
        print("\n📋 Próximos passos:")
        print("1. Adicionar rota de listagem em listas.py")
        print("2. Implementar lógica de cálculo no relatório misto")

if __name__ == "__main__":
    criar_tabela_provisoes()
