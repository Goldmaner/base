"""
Script melhorado para listar rotas sem decorator em cada blueprint
"""
import os
import re

# Mapeamento de arquivos para módulos de acesso
MODULOS = {
    'instrucoes.py': 'instrucoes',
    'analises.py': 'analises',
    'orcamento.py': 'orcamento',
    'parcerias.py': 'parcerias',
    'pesquisa_parcerias.py': 'pesquisa_parcerias',
    'parcerias_notificacoes.py': 'parcerias_notificacoes',
    'listas.py': 'listas',
    'conc_bancaria.py': 'conc_bancaria',
    'conc_rendimentos.py': 'conc_rendimentos',
    'conc_contrapartida.py': 'conc_contrapartida',
    'conc_relatorio.py': 'conc_relatorio',
}

def analisar_arquivo(caminho, modulo):
    """
    Analisa um arquivo e lista rotas que precisam do decorator
    """
    with open(caminho, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    rotas_sem_decorator = []
    rotas_com_decorator = []
    tem_import = False
    
    # Verificar import
    for linha in linhas:
        if 'from decorators import requires_access' in linha:
            tem_import = True
            break
    
    # Analisar rotas
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        
        # Encontrou uma rota
        if '@' in linha and '_bp.route' in linha:
            rota_linha = linha.strip()
            i += 1
            
            # Verificar as próximas linhas para @login_required e @requires_access
            tem_login = False
            tem_requires = False
            nome_funcao = ''
            
            while i < len(linhas) and (linhas[i].strip().startswith('@') or linhas[i].strip().startswith('def')):
                linha_atual = linhas[i].strip()
                
                if '@login_required' in linha_atual:
                    tem_login = True
                elif '@requires_access' in linha_atual:
                    tem_requires = True
                elif linha_atual.startswith('def '):
                    match = re.match(r'def\s+([a-z_]+)\(', linha_atual)
                    if match:
                        nome_funcao = match.group(1)
                    break
                
                i += 1
            
            # Se tem @login_required mas não tem @requires_access
            if tem_login and not tem_requires and nome_funcao:
                rotas_sem_decorator.append({
                    'rota': rota_linha,
                    'funcao': nome_funcao,
                    'linha': i - 1
                })
            elif tem_login and tem_requires:
                rotas_com_decorator.append(nome_funcao)
        
        i += 1
    
    return {
        'tem_import': tem_import,
        'sem_decorator': rotas_sem_decorator,
        'com_decorator': rotas_com_decorator
    }

def main():
    """
    Analisa todos os blueprints e lista o que precisa ser feito
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    routes_dir = os.path.join(base_dir, 'routes')
    
    print("=" * 80)
    print("ANÁLISE DE DECORATORS DE CONTROLE DE ACESSO")
    print("=" * 80)
    
    total_sem_decorator = 0
    total_com_decorator = 0
    
    for arquivo, modulo in MODULOS.items():
        caminho = os.path.join(routes_dir, arquivo)
        
        if not os.path.exists(caminho):
            print(f"\n✗ {arquivo} - NÃO ENCONTRADO")
            continue
        
        resultado = analisar_arquivo(caminho, modulo)
        
        print(f"\n📄 {arquivo} (módulo: {modulo})")
        print("-" * 80)
        
        if not resultado['tem_import']:
            print("  ⚠️  FALTA IMPORT: from decorators import requires_access")
        else:
            print("  ✓ Import presente")
        
        if resultado['sem_decorator']:
            print(f"\n  🔴 {len(resultado['sem_decorator'])} rota(s) SEM decorator:")
            for info in resultado['sem_decorator']:
                print(f"     • Linha {info['linha']}: {info['funcao']}() - {info['rota']}")
            total_sem_decorator += len(resultado['sem_decorator'])
        
        if resultado['com_decorator']:
            print(f"\n  ✓ {len(resultado['com_decorator'])} rota(s) COM decorator")
            total_com_decorator += len(resultado['com_decorator'])
    
    print("\n" + "=" * 80)
    print("RESUMO GERAL:")
    print(f"  - Rotas COM decorator: {total_com_decorator}")
    print(f"  - Rotas SEM decorator: {total_sem_decorator}")
    
    if total_sem_decorator > 0:
        print(f"\n  ⚠️  PENDENTE: Aplicar decorator em {total_sem_decorator} rotas")
    else:
        print("\n  ✅ TODOS OS DECORATORS APLICADOS!")
    print("=" * 80)

if __name__ == '__main__':
    main()
