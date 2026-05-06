with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

idx_func = content.find(b'def dgp_alteracoes')

old = (
    b'            total_count=total_count\r\n'
    b'        )\r\n'
    b'        \r\n'
    b'    except Exception as e:\r\n'
    b'        import traceback\r\n'
    b'        traceback.print_exc()\r\n'
)

new = (
    b'            total_count=total_count,\r\n'
    b'            filtro_osc=filtro_osc,\r\n'
    b'            filtro_processo=filtro_processo\r\n'
    b'        )\r\n'
    b'        \r\n'
    b'    except Exception as e:\r\n'
    b'        import traceback\r\n'
    b'        traceback.print_exc()\r\n'
)

idx = content.find(old, idx_func)
print('Match at:', idx)
if idx >= 0:
    content = content[:idx] + new + content[idx + len(old):]
    print('Applied')

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
