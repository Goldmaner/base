"""
Script para permitir atualização manual de responsáveis em termos rescindidos existentes
"""
import sys
sys.path.insert(0, '..')

from db import get_cursor, get_db

def listar_rescisoes_sem_responsavel():
    """Lista rescisões que ainda não têm responsável"""
    cur = get_cursor()
    
    cur.execute("""
        SELECT tr.id, tr.numero_termo, tr.data_rescisao, tr.sei_rescisao,
               tr.responsavel_rescisao, p.osc
        FROM public.termos_rescisao tr
        LEFT JOIN public.parcerias p ON tr.numero_termo = p.numero_termo
        WHERE tr.responsavel_rescisao IS NULL OR tr.responsavel_rescisao = ''
        ORDER BY tr.data_rescisao DESC
    """)
    
    rescisoes = cur.fetchall()
    cur.close()
    
    if not rescisoes:
        print("✅ Todas as rescisões já possuem responsável cadastrado!")
        return []
    
    print(f"\n📋 Rescisões sem responsável: {len(rescisoes)}")
    print("=" * 100)
    for r in rescisoes:
        print(f"ID: {r['id']} | Termo: {r['numero_termo']} | Data: {r['data_rescisao']} | OSC: {r['osc'] or 'N/A'}")
    print("=" * 100)
    
    return rescisoes


def listar_analistas_dgp():
    """Lista todos os analistas DGP (ativos e inativos)"""
    cur = get_cursor()
    
    cur.execute("""
        SELECT nome_analista, status
        FROM categoricas.c_dac_dgp_analistas
        ORDER BY nome_analista
    """)
    
    analistas = cur.fetchall()
    cur.close()
    
    print("\n👥 Analistas DGP disponíveis:")
    for i, a in enumerate(analistas, 1):
        status_str = "✓ Ativo" if a['status'] else "✗ Inativo"
        print(f"  {i}. {a['nome_analista']} ({status_str})")
    
    return analistas


def atualizar_responsavel(id_rescisao, responsavel):
    """Atualiza o responsável de uma rescisão"""
    cur = get_cursor()
    
    try:
        cur.execute("""
            UPDATE public.termos_rescisao
            SET responsavel_rescisao = %s
            WHERE id = %s
        """, (responsavel, id_rescisao))
        
        get_db().commit()
        cur.close()
        
        print(f"✅ Responsável atualizado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar: {str(e)}")
        get_db().rollback()
        return False


def main():
    print("=" * 100)
    print("ATUALIZAÇÃO DE RESPONSÁVEIS - TERMOS RESCINDIDOS")
    print("=" * 100)
    
    # Listar rescisões sem responsável
    rescisoes = listar_rescisoes_sem_responsavel()
    
    if not rescisoes:
        return
    
    # Listar analistas disponíveis
    analistas = listar_analistas_dgp()
    
    if not analistas:
        print("❌ Não há analistas DGP cadastrados!")
        return
    
    print("\n" + "=" * 100)
    print("INSTRUÇÕES:")
    print("Você pode atualizar via SQL ou pela interface web (/parcerias/rescisoes)")
    print("=" * 100)
    
    print("\nComando SQL para atualizar em massa (exemplo):")
    print("""
UPDATE public.termos_rescisao 
SET responsavel_rescisao = 'NOME_DO_ANALISTA'
WHERE responsavel_rescisao IS NULL;
    """)
    
    print("\nOu atualize individualmente pela interface web usando o botão 'Editar'.")


if __name__ == "__main__":
    main()
