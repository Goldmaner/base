"""
Script para verificar registros da tabela c_dac_despesas_provisao
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from db import get_cursor

with app.app_context():
    cursor = get_cursor()
    
    # Contar total
    cursor.execute('SELECT COUNT(*) FROM categoricas.c_dac_despesas_provisao')
    result = cursor.fetchone()
    total = result['count'] if isinstance(result, dict) else result[0]
    print(f'✅ Total de provisões cadastradas: {total}')
    
    # Listar todas
    cursor.execute('SELECT id, despesa_provisao, descricao FROM categoricas.c_dac_despesas_provisao ORDER BY despesa_provisao')
    provisoes = cursor.fetchall()
    
    print('\n📋 Lista de Provisões:')
    print('-' * 80)
    for p in provisoes:
        print(f'  {p["id"]:2d} | {p["despesa_provisao"]:30s} | {p["descricao"] or "Sem descrição"}')
    
    cursor.close()
    print('\n✨ Verificação concluída!')
