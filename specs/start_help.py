"""
Script auxiliar para iniciar os servidores
"""

print("""
╔════════════════════════════════════════════════════════════╗
║           FAF - Ferramenta de Análise Financeira          ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Para iniciar os servidores, abra dois terminais:         ║
║                                                            ║
║  🔧 DESENVOLVIMENTO (porta 8080):                          ║
║     python run_dev.py                                      ║
║     - Hot reload ATIVADO                                   ║
║     - Reinicia automaticamente ao editar                   ║
║     - Use para testar mudanças                             ║
║                                                            ║
║  🚀 PRODUÇÃO (porta 5000):                                 ║
║     python run_prod.py                                     ║
║     - Hot reload DESATIVADO                                ║
║     - Precisa reiniciar manualmente (Ctrl+C e rodar dnovo) ║
║     - Use para acesso dos usuários                         ║
║                                                            ║
║  📝 FLUXO DE TRABALHO:                                     ║
║     1. Deixe produção (5000) rodando para usuários         ║
║     2. Desenvolva na porta 8080                            ║
║     3. Quando terminar, faça git push                      ║
║     4. Reinicie o servidor de produção (5000)              ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
""")
