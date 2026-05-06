from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('templates'))
src = env.loader.get_source(env, 'dgp_kanban.html')[0]
env.parse(src)
print('Template OK, chars:', len(src))
