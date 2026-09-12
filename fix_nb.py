import json
import os

nb1_path = r'backend/app/models/01_DualStem_Training.ipynb'
with open(nb1_path, 'r', encoding='utf-8') as f:
    nb1 = json.load(f)

changed = False
for cell in nb1['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        if 'RUN_SAVE_DIR =' in source:
            lines = source.split('\n')
            new_lines = []
            for line in lines:
                if line.strip().startswith('RUN_SAVE_DIR ='):
                    line = 'RUN_SAVE_DIR = os.path.join(r"D:\\CS-Senior26\'\\GR\\martial-arts-trainer\\backend\\app\\models\\Results", "thesis_results")'
                    changed = True
                new_lines.append(line)
            source = '\n'.join(new_lines)
            
        if '\n' in source:
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source']:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')
        else:
            cell['source'] = [source]

if changed:
    with open(nb1_path, 'w', encoding='utf-8') as f:
        json.dump(nb1, f, indent=1)
    print('Updated RUN_SAVE_DIR')
else:
    print('Could not find RUN_SAVE_DIR')
