print('Iniciando implementação do campo ativo...')
import re
content = open('core/models.py', 'r', encoding='utf-8').read()
pattern = r'(class EscalaMilitar\\(models\\.Model\\):.*?)(\\n    class Meta:)'
match = re.search(pattern, content, re.DOTALL)
new_content = match.group(1) + '\\n    ativo = models.BooleanField(default=True, verbose_name=\
Ativo\, help_text=\Desmarque
para
desativar
este
militar
desta
escala
específica\)\\n' + match.group(2)
content = re.sub(pattern, new_content, content, flags=re.DOTALL)
open('core/models.py', 'w', encoding='utf-8').write(content)
