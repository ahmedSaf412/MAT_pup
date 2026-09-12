import os, glob

renames = [
    (r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\Andrew's_correction", r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\MADS_correction"),
    (r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\scripts\extract_mads_sequence_andrew.py", r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\scripts\extract_mads_sequence.py"),
    (r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\app\rag\data\andrew_reference_sequences.json", r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\app\rag\data\mads_reference_sequences.json")
]

for src, dst in renames:
    if os.path.exists(src):
        os.rename(src, dst)
        print(f"Renamed {src} to {dst}")

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
    
    if 'andrew' not in content.lower():
        return
        
    new_content = content.replace("Andrew's", "MADS")
    new_content = new_content.replace("Andrews", "MADS")
    new_content = new_content.replace("Andrew", "MADS")
    new_content = new_content.replace("andrew", "mads")
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Replaced in {filepath}")

search_dirs = [
    r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\app",
    r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\scripts",
    r"D:\CS-Senior26'\GR\martial-arts-trainer\backend\MADS_correction"
]

for d in search_dirs:
    for root, dirs, files in os.walk(d):
        if '__pycache__' in root: continue
        for file in files:
            if file.endswith('.py') or file.endswith('.json') or file.endswith('.md'):
                replace_in_file(os.path.join(root, file))

print("Done replacing.")
