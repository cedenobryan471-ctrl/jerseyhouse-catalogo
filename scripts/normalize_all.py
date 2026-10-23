"""Aplica todas las reglas de limpieza y orden al catálogo. Se corre después de cada carga."""
import os, subprocess, sys
env = dict(os.environ, PYTHONPATH='scripts')
for script in ['clean_titles.py', 'fix_sections.py', 'fix_casual.py', 'spanish_names.py', 'regroup_footwear.py', 'assign_tones.py']:
    subprocess.run([sys.executable, f'scripts/{script}'], check=True, env=env)
