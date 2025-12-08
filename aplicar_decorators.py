"""
Script para aplicar decorators de controle de acesso em todos os blueprints
"""
import re
import os

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
    'despesas.py': 'portarias',  # Assumindo que despesas usa portarias
}

def processar_arquivo(caminho, modulo):
    """
    Processa um arquivo de blueprint para adicionar o import e decorators
    """
    with open(caminho, 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    original = conteudo
    
    # 1. Adicionar import se não existir
    if 'from decorators import requires_access' not in conteudo:
        # Encontrar a seção de imports
        padrao_imports = r'(from utils import login_required)'
        if re.search(padrao_imports, conteudo):
            conteudo = re.sub(
                padrao_imports,
                r'\1\nfrom decorators import requires_access',
                conteudo,
                count=1
            )
            print(f"  ✓ Import adicionado em {os.path.basename(caminho)}")
        else:
            print(f"  ⚠ Não encontrou 'from utils import login_required' em {os.path.basename(caminho)}")
    
    # 2. Adicionar decorator após @login_required em todas as rotas
    # Padrão: @rota\n@login_required\ndef funcao():
    # Transforma em: @rota\n@login_required\n@requires_access('modulo')\ndef funcao():
    
    padrao_rota = rf'(@[a-z_]+_bp\.route\([^\)]+\)\s*\n@login_required)\s*\n(def [a-z_]+\()'
    
    def substituir_decorator(match):
        decorators = match.group(1)
        funcao = match.group(2)
        # Verificar se já tem @requires_access
        if '@requires_access' in match.group(0):
            return match.group(0)
        return f"{decorators}\n@requires_access('{modulo}')\n{funcao}"
    
    conteudo_novo = re.sub(padrao_rota, substituir_decorator, conteudo, flags=re.MULTILINE)
    
    if conteudo_novo != original:
        with open(caminho, 'w', encoding='utf-8') as f:
            f.write(conteudo_novo)
        
        # Contar quantos decorators foram adicionados
        decorators_adicionados = conteudo_novo.count('@requires_access') - original.count('@requires_access')
        if decorators_adicionados > 0:
            print(f"  ✓ {decorators_adicionados} decorator(s) aplicado(s) em {os.path.basename(caminho)}")
        return True
    else:
        print(f"  → Nenhuma alteração necessária em {os.path.basename(caminho)}")
        return False

def main():
    """
    Aplica decorators em todos os blueprints
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    routes_dir = os.path.join(base_dir, 'routes')
    
    print("=" * 60)
    print("APLICANDO DECORATORS DE CONTROLE DE ACESSO")
    print("=" * 60)
    
    arquivos_processados = 0
    arquivos_modificados = 0
    
    for arquivo, modulo in MODULOS.items():
        caminho = os.path.join(routes_dir, arquivo)
        
        if not os.path.exists(caminho):
            print(f"✗ Arquivo não encontrado: {arquivo}")
            continue
        
        print(f"\n📄 Processando {arquivo} (módulo: {modulo})")
        arquivos_processados += 1
        
        if processar_arquivo(caminho, modulo):
            arquivos_modificados += 1
    
    print("\n" + "=" * 60)
    print(f"RESUMO:")
    print(f"  - Arquivos processados: {arquivos_processados}")
    print(f"  - Arquivos modificados: {arquivos_modificados}")
    print("=" * 60)

if __name__ == '__main__':
    main()
