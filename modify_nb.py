import json
import os

nb1_path = r'backend/app/models/01_DualStem_Training.ipynb'
with open(nb1_path, 'r', encoding='utf-8') as f:
    nb1 = json.load(f)

for cell in nb1['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        # 1. Update RUN_SAVE_DIR to 'thesis_results'
        if 'RUN_SAVE_DIR = os.path.join' in source and 'Run_{timestamp}' in source:
            source = source.replace(
                'RUN_SAVE_DIR = os.path.join(r"D:\\CS-Senior26\'\\GR\\martial-arts-trainer\\backend\\app\\models\\Results", f"Run_{timestamp}")',
                'RUN_SAVE_DIR = os.path.join(r"D:\\CS-Senior26\'\\GR\\martial-arts-trainer\\backend\\app\\models\\Results", "thesis_results")'
            )
            
        # 2. Remove SVM & KNN and their imports
        if '"SVM (RBF Kernel)": SVC' in source:
            lines = source.split('\n')
            new_lines = []
            for line in lines:
                if '"SVM (RBF Kernel)": SVC' in line or '"KNN (K=5)": KNeighborsClassifier' in line:
                    continue
                if 'from sklearn.svm import SVC' in line or 'from sklearn.neighbors import KNeighborsClassifier' in line:
                    continue
                new_lines.append(line)
            source = '\n'.join(new_lines)
            
            source = source.replace('"XGBoost", "Random Forest", "SVM (RBF Kernel)", "KNN (K=5)"', '"XGBoost", "Random Forest"')
            source = source.replace("'SVM (RBF Kernel)': '#FFD3B6',", "")
            source = source.replace("'KNN (K=5)': '#FFAAA5'", "")
            
        # 3. Fix temporal shift iteration
        if 'for name in ["XGBoost", "Random Forest", "SVM (RBF Kernel)", "KNN (K=5)"]:' in source:
            source = source.replace(
                'for name in ["XGBoost", "Random Forest", "SVM (RBF Kernel)", "KNN (K=5)"]:',
                'for name in ["XGBoost", "Random Forest"]:'
            )
            
        # Write back line by line for jupyter format
        if '\n' in source:
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source']:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')
        else:
            cell['source'] = [source]

with open(nb1_path, 'w', encoding='utf-8') as f:
    json.dump(nb1, f, indent=1)


nb2_path = r'backend/app/models/Analysis/00_Data_AnalysisV2.ipynb'
with open(nb2_path, 'r', encoding='utf-8') as f:
    nb2 = json.load(f)

for cell in nb2['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        
        # Add output dir setup
        if 'CSV_PATH = r' in source and 'OUT_DIR' not in source:
            source = source + '\n\nimport os\nOUT_DIR = r"D:\\CS-Senior26\'\\GR\\martial-arts-trainer\\backend\\app\\models\\Results\\thesis_results"\nos.makedirs(OUT_DIR, exist_ok=True)\n'
            
        # Redirect savefig to thesis_results
        if 'plt.savefig(' in source:
            source = source.replace("plt.savefig('", "plt.savefig(os.path.join(OUT_DIR, '")
            source = source.replace("', dpi=", "'), dpi=")
            
        # Write back line by line for jupyter format
        if '\n' in source:
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source']:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')
        else:
            cell['source'] = [source]

with open(nb2_path, 'w', encoding='utf-8') as f:
    json.dump(nb2, f, indent=1)

print("Modification complete.")
